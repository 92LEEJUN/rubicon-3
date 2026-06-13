"""레거시 오케스트레이터 — LLM tool-loop 데모(CLI용).

OpenAI function calling으로 tool을 자유 호출하는 프로토타입 경로. 내부 API의 결정적 경로는
`CapabilityOrchestrator`(플래너 없음, 옛 core.Orchestrator를 수렴·대체 — ADR-0048·§12.3)를 쓴다.
본 모듈의 `astream_turn`은 LLM_BACKED on·MULTIAGENT off일 때의 prose 경로로 아직 쓰이며,
`run`은 CLI 데모용이다.
"""
import asyncio
import json
import uuid
from typing import AsyncIterator, Optional

from ..llm import MODEL, achat_completion, get_client
from ..tools import TOOLS, call

SYSTEM = (
    "당신은 삼성 가전 AI 컨시어지입니다. 사용자의 가전 문제를 진단하고, "
    "근거 기반 해결 가이드를 제시하며, 필요한 부품 주문까지 자연스럽게 잇습니다.\n"
    "원칙:\n"
    "1) 기기 상태·해결법·부품은 반드시 제공된 tool을 호출해 얻은 결과만 근거로 사용한다(추측 금지).\n"
    "2) 해결 가이드는 번호 단계로 제시하고, 위험 단계가 있으면 주의를 표시한다.\n"
    "3) 해결에 부품이 필요하면 match_parts로 확인 후, 가격·재고와 함께 주문을 제안한다.\n"
    "4) 재고가 없으면 입고 알림/대체를, 직접 해결이 어려우면 방문/상담 연결을 안내한다.\n"
    "5) 한국어로 간결하고 친절하게 답한다."
)

INTENT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "intent_result",
        "schema": {
            "type": "object",
            "properties": {
                "intents": {
                    "type": "array",
                    "items": {"type": "string",
                              "enum": ["device_status", "troubleshoot", "order", "recommend", "general"]},
                },
                "is_compound": {"type": "boolean"},
            },
            "required": ["intents", "is_compound"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


def classify(user_message: str) -> dict:
    """① 의도 분류·분해 (구조화 출력)."""
    resp = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "사용자 입력의 의도를 분류·분해한다."},
            {"role": "user", "content": user_message},
        ],
        response_format=INTENT_SCHEMA,
    )
    return json.loads(resp.choices[0].message.content)


async def aclassify(user_message: str) -> dict:
    """① 의도 분류·분해 (구조화 출력) — 비동기."""
    resp = await achat_completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": "사용자 입력의 의도를 분류·분해한다."},
            {"role": "user", "content": user_message},
        ],
        response_format=INTENT_SCHEMA,
    )
    return json.loads(resp.choices[0].message.content)


def _memory_note(memory: Optional[dict]) -> Optional[dict]:
    """워킹 컨텍스트(요약+사실)를 system 노트로 — 이어가기 주입(ADR-0040, 컴패니언 §0.4)."""
    if not memory:
        return None
    summary = (memory.get("summary") or "").strip()
    facts = memory.get("facts") or {}
    if not summary and not facts:
        return None
    parts = []
    if summary:
        parts.append(f"요약: {summary}")
    if facts:
        parts.append(f"사실: {facts}")
    return {"role": "system", "content": "[이전 대화 맥락 — 이어서 응대]\n" + "\n".join(parts)}


async def arun(user_message: str, max_steps: int = 6, verbose: bool = False,
               memory: Optional[dict] = None) -> str:
    """LLM tool-loop — 비동기(서빙 경로). 실행은 순차 유지(출력 동일)."""
    intent = await aclassify(user_message)
    if verbose:
        print(f"[의도] {intent}")

    messages = [{"role": "system", "content": SYSTEM}]
    note = _memory_note(memory)
    if note:
        messages.append(note)
    messages.append({"role": "user", "content": user_message})

    for _ in range(max_steps):
        resp = await achat_completion(
            model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto",
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content or ""
        # 도구 호출 → Mock 실행 → 결과 회신 (tool은 결정적·즉시)
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result = call(tc.function.name, args)
            if verbose:
                print(f"[tool] {tc.function.name}({args}) -> {json.dumps(result, ensure_ascii=False)[:120]}…")
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
    # 루프 한계 — 마지막 한 번 더 생성
    final = await achat_completion(model=MODEL, messages=messages)
    return final.choices[0].message.content or ""


def run(user_message: str, max_steps: int = 6, verbose: bool = True) -> str:
    """CLI 동기 진입점 — 내부 비동기 tool-loop을 실행(루프 외부 호출 전제)."""
    return asyncio.run(arun(user_message, max_steps=max_steps, verbose=verbose))


async def astream_turn(message: str, screen_context: Optional[dict] = None,
                       memory: Optional[dict] = None) -> AsyncIterator[dict]:
    """LLM 자연어 답변 경로(비동기) — api-contract §2.1 봉투(delta → done).

    tool-loop으로 근거(기기·해결·부품 Mock)를 모아 자연어 답변을 생성하고,
    텍스트를 `delta` 청크로 흘린 뒤 `done`으로 종료한다(실패 시 error 폴백, R13).
    `memory`(이전 맥락 요약+사실)가 있으면 이어가기로 주입한다(컴패니언 §0.4).
    """
    try:
        answer = await arun(message, verbose=False, memory=memory)
    except Exception as exc:  # 전체 폴백(R13) — 대화 중단 금지
        yield {"type": "error", "code": "orchestrator_error",
               "fallback": {"kind": "text",
                            "data": {"message": "일시적인 문제가 발생했어요. 잠시 후 다시 시도해 주세요."}},
               "detail": str(exc)}
        return
    yield {"type": "delta", "text": answer}
    yield {"type": "flow", "active_flow": None}
    yield {"type": "done", "message_id": f"msg_{uuid.uuid4().hex[:8]}"}

"""오케스트레이터 — orchestration.md 파이프라인의 소형 프로토타입.

흐름: ① 의도 분류(구조화 출력) → ② tool 호출 루프(기기·CS·부품) → ③ 근거 기반 응답.
근거(기기 상태·CS 단계·부품)는 tool 결과에서만 가져온다(환각 억제).
"""
import json
from .llm import client, MODEL
from .tools import TOOLS, call

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
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "사용자 입력의 의도를 분류·분해한다."},
            {"role": "user", "content": user_message},
        ],
        response_format=INTENT_SCHEMA,
    )
    return json.loads(resp.choices[0].message.content)


def run(user_message: str, max_steps: int = 6, verbose: bool = True) -> str:
    intent = classify(user_message)
    if verbose:
        print(f"[의도] {intent}")

    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_message}]

    for _ in range(max_steps):
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto",
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content or ""
        # 도구 호출 → Mock 실행 → 결과 회신
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
    final = client.chat.completions.create(model=MODEL, messages=messages)
    return final.choices[0].message.content or ""

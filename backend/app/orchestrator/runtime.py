"""멀티에이전트 서빙 런타임 — 슈퍼바이저-워커, async·스트리밍 (specs/multi-agent-runtime).

벤치(`multiagent.py`)의 단계 흐름을 **async·스트리밍**으로 재배선한다(ADR-0009·0011·0012·0016).
- 순차·단일 패스 유지(병렬화는 ADR-0017 보류=비범위).
- 모든 LLM 호출은 `achat_completion`(AsyncOpenAI+세마포어+백오프) 경유.
- 출력은 api-contract §2.1 봉투(delta/flow/done/error). 프롬프트는 prompts.py 단일 출처(ADR-0013).

오케스트레이션 판정(`plan_workers`·`should_review`)은 LLM과 분리해 결정적으로 테스트 가능하다.
"""
from __future__ import annotations

import json
import uuid
from typing import AsyncIterator, Optional

from ..llm import MODEL, achat_completion
from ..tools import TOOLS, call
from .legacy import INTENT_SCHEMA, SYSTEM, _memory_note
from .prompts import COMMERCE_PROMPT, DIAGNOSIS_PROMPT, RECOMMEND_PROMPT, REVIEW_PROMPT

# 의도 우선순위(core._PRIORITY와 정합: 안전/CS 먼저, order 뒤)
_PRIORITY = {"device_status": 0, "troubleshoot": 1, "general": 2, "recommend": 3, "order": 4}
_DIAG_TOOLS = ("get_device_status", "search_solutions")
_COMM_TOOLS = ("match_parts",)
_RECO_TOOLS = ("recommend", "match_parts")


# ── 결정적 오케스트레이션 판정(LLM 무관, 단위 테스트 대상) ────────────────────
def plan_workers(intents: list[str]) -> list[str]:
    """정렬된 의도 → 워커 단계 목록(중복 제거·고정 순서: 진단→커머스→일반)."""
    stages: list[str] = []
    if any(i in ("device_status", "troubleshoot") for i in intents):
        stages.append("diagnosis")
    if "order" in intents:
        stages.append("commerce")
    if "recommend" in intents:
        stages.append("recommend")              # 자연어 추천 = agent(ADR-0044)
    if "general" in intents or not stages:
        stages.append("general")
    return stages


def should_review(intents: list[str], *, safety: bool = False, uncertain: bool = False) -> bool:
    """조건부 리뷰 발동(ADR-0011) — 커밋(order, R17)·안전(R23)·불확실(R16)일 때만."""
    return ("order" in intents) or safety or uncertain


def _extract_required_parts(tool_result: dict) -> list[str]:
    """search_solutions 결과에서 required_parts 추출(진단→커머스 핸드오프)."""
    out: list[str] = []
    sols = tool_result.get("solutions") if isinstance(tool_result, dict) else None
    for s in sols or []:
        out += (s.get("required_parts") or []) if isinstance(s, dict) else []
    out += tool_result.get("required_parts", []) if isinstance(tool_result, dict) else []
    return out


# ── 워커 tool-loop (async) ────────────────────────────────────────────────────
async def _run_worker(system: str, message: str, allowed: tuple,
                      memory: Optional[dict] = None, max_steps: int = 4) -> tuple[str, list[str]]:
    tools = [t for t in TOOLS if t["function"]["name"] in allowed]
    messages = [{"role": "system", "content": system}]
    note = _memory_note(memory)
    if note:
        messages.append(note)
    messages.append({"role": "user", "content": message})
    required_parts: list[str] = []
    for _ in range(max_steps):
        resp = await achat_completion(model=MODEL, messages=messages,
                                      tools=tools or None, tool_choice="auto" if tools else None)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content or "", required_parts
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result = call(tc.function.name, args)
            if tc.function.name == "search_solutions":
                required_parts += _extract_required_parts(result)
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    final = await achat_completion(model=MODEL, messages=messages)
    return final.choices[0].message.content or "", required_parts


async def _general(message: str, memory: Optional[dict]) -> str:
    """추천·일반 — 전용 워커 없이 직접 응답(tools.py 미보유 도구는 비범위)."""
    messages = [{"role": "system", "content": SYSTEM}]
    note = _memory_note(memory)
    if note:
        messages.append(note)
    messages.append({"role": "user", "content": message})
    resp = await achat_completion(model=MODEL, messages=messages)
    return resp.choices[0].message.content or ""


# ── 서빙 진입점 (legacy.astream_turn과 동일 계약) ─────────────────────────────
async def astream_multiagent(message: str, screen_context: Optional[dict] = None,
                             memory: Optional[dict] = None) -> AsyncIterator[dict]:
    """슈퍼바이저-워커 다단계 스트리밍. delta를 단계별로 점진 방출 → done(실패 시 error 폴백)."""
    try:
        result = await aclassify(message)
        intents = sorted(result.get("intents", []), key=lambda i: _PRIORITY.get(i, 9))
    except Exception as exc:  # 분해 실패 = 턴 회복 불가 → error 폴백(대화 중단 금지)
        yield {"type": "error", "code": "orchestrator_error",
               "fallback": {"kind": "text", "data": {"message": "일시적인 문제가 발생했어요. 잠시 후 다시 시도해 주세요."}},
               "detail": str(exc)}
        return

    carried_parts: list[str] = []
    for stage in plan_workers(intents):
        try:
            if stage == "diagnosis":
                text, parts = await _run_worker(DIAGNOSIS_PROMPT, message, _DIAG_TOOLS, memory)
                carried_parts += parts
            elif stage == "commerce":
                cmsg = message + (f"\n[필요 부품 후보: {carried_parts}]" if carried_parts else "")
                text, _ = await _run_worker(COMMERCE_PROMPT, cmsg, _COMM_TOOLS, memory)
            elif stage == "recommend":
                text, _ = await _run_worker(RECOMMEND_PROMPT, message, _RECO_TOOLS, memory)
            else:  # general
                text = await _general(message, memory)
        except Exception:  # 단계 실패 = 부분 폴백(이미 방출분 유지, 나머지 계속)
            yield {"type": "delta", "text": "(이 부분은 잠시 후 다시 도와드릴게요.)"}
            continue
        if text:
            yield {"type": "delta", "text": text}

    # 조건부 리뷰(단일 패스) — 발동 시 검수, 위반은 보정 노트(재실행 없음)
    if should_review(intents):
        try:
            note = await _review(message)
            if note:
                yield {"type": "delta", "text": note}
        except Exception:
            pass  # 리뷰 실패 = 초안 유지(R13)

    yield {"type": "flow", "active_flow": None}
    yield {"type": "done", "message_id": f"msg_{uuid.uuid4().hex[:8]}"}


async def aclassify(message: str) -> dict:
    """의도 분해(구조화 출력) — legacy INTENT_SCHEMA 재사용."""
    resp = await achat_completion(model=MODEL, response_format=INTENT_SCHEMA, messages=[
        {"role": "system", "content": "사용자 입력의 의도를 분류·분해한다."},
        {"role": "user", "content": message}])
    return json.loads(resp.choices[0].message.content)


async def _review(message: str) -> str:
    """조건부 리뷰 — 안전/근거/정책 검수. 위반 시 보정 노트(없으면 빈 문자열)."""
    resp = await achat_completion(model=MODEL, messages=[
        {"role": "system", "content": REVIEW_PROMPT},
        {"role": "user", "content": f"다음 응답을 안전·근거·정책 관점에서 한 줄로 검수(문제없으면 빈 줄): {message}"}])
    return (resp.choices[0].message.content or "").strip()

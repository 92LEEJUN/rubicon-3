"""멀티에이전트 러너(slim) — 슈퍼바이저-워커 + 조건부 리뷰(docs/agents.md), 단계별 타이밍 계측.

목적: 멀티에이전트 구조에서 **툴콜 누적 시 실제 지연(최대 몇 초)** 을 실측한다.
모든 LLM 호출은 Phase A 래퍼(llm.chat_completion: 동시성 세마포어 + 백오프)를 탄다.
런타임 배선(스트리밍 계약)은 별도; 본 모듈은 구조·지연 검증/벤치용이다.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from ..llm import MODEL, chat_completion
from ..tools import TOOLS, call
from .legacy import INTENT_SCHEMA
from .prompts import COMMERCE_PROMPT, DIAGNOSIS_PROMPT, REVIEW_PROMPT

_DIAG_TOOLS = ("get_device_status", "search_solutions")
_COMM_TOOLS = ("match_parts",)


@dataclass
class StageTiming:
    name: str
    seconds: float
    llm_calls: int
    tool_calls: int
    max_llm_call: float


@dataclass
class TurnResult:
    intents: list
    stages: list = field(default_factory=list)
    total_seconds: float = 0.0

    @property
    def total_llm(self) -> int:
        return sum(s.llm_calls for s in self.stages)

    @property
    def total_tool(self) -> int:
        return sum(s.tool_calls for s in self.stages)

    @property
    def max_llm_call(self) -> float:
        return max((s.max_llm_call for s in self.stages), default=0.0)


def _agent(system: str, user_msg: str, allowed: tuple | None = None, max_steps: int = 4) -> StageTiming:
    """단일 에이전트 tool-loop — 허용 tool만 노출, LLM 라운드트립/툴콜 계측."""
    tools = [t for t in TOOLS if allowed is None or t["function"]["name"] in allowed]
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_msg}]
    t_stage = time.time()
    n_llm = n_tool = 0
    max_call = 0.0
    for _ in range(max_steps):
        t0 = time.time()
        resp = chat_completion(model=MODEL, messages=messages,
                               tools=tools or None, tool_choice="auto" if tools else None)
        dt = time.time() - t0
        max_call = max(max_call, dt)
        n_llm += 1
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return StageTiming("", time.time() - t_stage, n_llm, n_tool, max_call)
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            n_tool += 1
            args = json.loads(tc.function.arguments or "{}")
            result = call(tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    # 루프 한계 — 마지막 생성 1회
    t0 = time.time()
    chat_completion(model=MODEL, messages=messages)
    max_call = max(max_call, time.time() - t0)
    n_llm += 1
    return StageTiming("", time.time() - t_stage, n_llm, n_tool, max_call)


def run_multiagent(message: str) -> TurnResult:
    """슈퍼바이저 분해 → (진단·커머스) → 조건부 리뷰. 단계별/총 지연을 반환."""
    t_total = time.time()

    # 1) Supervisor — 의도 분해(구조화 출력). strict 스키마에 맞춘 간결 분류 지시.
    #    (SUPERVISOR_PROMPT 역할 정의는 위임/조립용. 구조화 분류 호출은 스키마 정합 지시를 쓴다.)
    t0 = time.time()
    resp = chat_completion(model=MODEL, response_format=INTENT_SCHEMA, messages=[
        {"role": "system", "content":
            "사용자 입력의 의도를 분류·분해한다. 가전 도메인 의도: "
            "device_status, troubleshoot, order, recommend, general."},
        {"role": "user", "content": message}])
    sup_dt = time.time() - t0
    intents = json.loads(resp.choices[0].message.content).get("intents", [])
    res = TurnResult(intents=intents)
    res.stages.append(StageTiming("supervisor", sup_dt, 1, 0, sup_dt))

    has_order = "order" in intents

    # 2) 워커 위임(우선순위: 안전/CS 먼저)
    if any(i in ("troubleshoot", "device_status") for i in intents):
        st = _agent(DIAGNOSIS_PROMPT, message, _DIAG_TOOLS)
        st.name = "diagnosis"
        res.stages.append(st)
    if has_order:
        st = _agent(COMMERCE_PROMPT, message, _COMM_TOOLS)
        st.name = "commerce"
        res.stages.append(st)

    # 3) Review — 조건부(커밋/안전/불확실). 여기선 주문(커밋) 포함 시 발동
    if has_order:
        t0 = time.time()
        chat_completion(model=MODEL, messages=[
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": f"다음 응답 초안을 검수하세요(주문 포함):\n{message}"}])
        rv = time.time() - t0
        res.stages.append(StageTiming("review", rv, 1, 0, rv))

    res.total_seconds = time.time() - t_total
    return res

"""슈퍼바이저 compose + 가드레일의 레이턴시 측정 — 총 E2E와 first-token(ADR-0053·0054).

측정 항목:
- **first-token** = astream에서 **첫 청크(섹션)** 가 나오기까지의 시간.
- **총 E2E** = 스트림을 끝까지 소진하는 시간.

실 LLM은 CI에 없으므로(OPENAI_API_KEY 부재) 라우팅/compose LLM 콜은 **시뮬레이션 지연**(stub)으로
모델링한다 — 구조적 델타(배리어·compose가 first-token/E2E에 더하는 비용)를 결정적으로 드러낸다.
가드레일(pre 병렬 screen·post 마스킹)은 **결정적 규칙**이라 실측 그대로다.

실행: cd backend && python verify_compose_timing.py
"""
import asyncio
import os
import statistics
import time

from app.orchestrator.capability import CapabilityOrchestrator, Plan
from app.orchestrator.classify import RuleBasedClassifier
from app.orchestrator.guardrail import Guardrail

# 복합 턴(처리 섹션 ≥2 → compose 발동): 진단 + 추천
MESSAGE = "세탁기에서 물이 안 빠져요. 그리고 새 공기청정기도 추천해줘"
CAPS = ["diagnose", "recommend"]

# 시뮬레이션 LLM 지연(초) — gpt-4o-mini 류 라우팅/짧은 종합의 현실적 범위
ROUTE_DELAY = float(os.getenv("SIM_ROUTE_S", "0.45"))     # apropose(라우팅 홉)
COMPOSE_DELAY = float(os.getenv("SIM_COMPOSE_S", "0.80"))  # acompose(종합 1콜)


class _SimSupervisor:
    """라우팅/종합 LLM 콜을 시뮬레이션 지연으로 모델링(네트워크 없이 구조적 비용 측정)."""

    def __init__(self, caps, route_delay, compose_delay):
        self.caps = caps
        self.route_delay = route_delay
        self.compose_delay = compose_delay

    async def apropose(self, catalog, message):
        await asyncio.sleep(self.route_delay)
        return Plan(capabilities=list(self.caps))

    async def acompose(self, message, plan, facts):
        await asyncio.sleep(self.compose_delay)
        return "진단 가이드와 추천을 한눈에 정리해 드렸어요. 아래 단계와 카드를 확인해 보세요."


def _orch(planner=None, guardrail=None):
    return CapabilityOrchestrator(classifier=RuleBasedClassifier(),
                                  llm_planner=planner, guardrail=guardrail)


async def _measure(orch, message):
    """(first_token_ms, total_ms) — 첫 청크까지 / 끝까지."""
    t0 = time.perf_counter()
    first = None
    async for _ in orch.astream(message):
        if first is None:
            first = (time.perf_counter() - t0) * 1000
    total = (time.perf_counter() - t0) * 1000
    return first, total


async def _run_case(label, orch, env, rounds):
    # env 토글 적용(매 호출 평가)
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    firsts, totals = [], []
    for _ in range(rounds):
        f, t = await _measure(orch, MESSAGE)
        firsts.append(f)
        totals.append(t)
    md = statistics.median
    print(f"  [{label}]")
    print(f"    · first-token : {md(firsts):7.1f} ms  (min {min(firsts):.0f} / max {max(firsts):.0f})")
    print(f"    · 총 E2E      : {md(totals):7.1f} ms  (min {min(totals):.0f} / max {max(totals):.0f})")
    return md(firsts), md(totals)


async def main(rounds=9):
    print("=" * 72)
    print(f"compose/guardrail 레이턴시 ({rounds}회 중앙값)")
    print(f"  시뮬레이션: 라우팅={ROUTE_DELAY*1000:.0f}ms · compose={COMPOSE_DELAY*1000:.0f}ms")
    print(f"  메시지: {MESSAGE}")
    print("=" * 72)

    sup = _SimSupervisor(CAPS, ROUTE_DELAY, COMPOSE_DELAY)
    guard = Guardrail()

    # A. 베이스라인 — 슈퍼바이저 라우팅만, compose/guardrail off(오늘 동작)
    fA, tA = await _run_case("A 베이스라인(라우팅만, COMPOSE off)", _orch(sup),
                             {"COMPOSE": None, "GUARDRAIL": None}, rounds)
    # B. compose on — 배리어 + 종합 1콜
    fB, tB = await _run_case("B compose on", _orch(sup),
                             {"COMPOSE": "1", "GUARDRAIL": None}, rounds)
    # C. compose on + guardrail on — pre 병렬 screen + post 마스킹
    fC, tC = await _run_case("C compose on + guardrail on", _orch(sup, guard),
                             {"COMPOSE": "1", "GUARDRAIL": "1"}, rounds)
    # D. 결정적 경로(시뮬레이션 LLM 0) — 가드레일 순수 오버헤드
    sup0 = _SimSupervisor(CAPS, 0.0, 0.0)
    await _run_case("D 가드레일 순수 오버헤드(LLM 0, guardrail on)", _orch(sup0, guard),
                    {"COMPOSE": None, "GUARDRAIL": "1"}, rounds)

    for k in ("COMPOSE", "GUARDRAIL"):
        os.environ.pop(k, None)

    print("\n" + "-" * 72)
    print("요약 (중앙값)")
    print(f"  · compose가 더하는 first-token : +{fB - fA:6.1f} ms  (배리어+종합 1콜)")
    print(f"  · compose가 더하는 총 E2E      : +{tB - tA:6.1f} ms")
    print(f"  · guardrail이 더하는 first-token: +{fC - fB:6.1f} ms  (pre 병렬 → ≈0 기대)")
    print(f"  · guardrail이 더하는 총 E2E     : +{tC - tB:6.1f} ms  (post 마스킹)")
    print("-" * 72)


if __name__ == "__main__":
    asyncio.run(main())

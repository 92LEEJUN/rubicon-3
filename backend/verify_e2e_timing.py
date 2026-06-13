"""E2E 실측 타이밍 — capability 경로의 구간별/총 시간(라우팅 홉 vs 실행).

(core.Orchestrator 패리티 비교는 core 제거(ADR-0048·§12.3)로 폐기 — 결정적 경로는 이제
CapabilityOrchestrator(planner=None) 단일.)

- 결정적 실행+스트림(LLM 없음): 베이스라인
- LLM 홉(apropose) 단독: 라우팅 1홉
- 실 총 E2E(LLM 플래너): 전체

실행: cd backend && LLM_BACKED=1 python verify_e2e_timing.py
"""
import asyncio
import os
import statistics
import time

from app.orchestrator.capability import CapabilityOrchestrator

TIMING_CORPUS = [
    ("clean 단일", "세탁기에서 물이 안 빠져요"),
    ("F2 보증/예약", "보증으로 무상 수리 되는지랑 기사 방문 예약도 가능한가요"),
    ("모호", "이거 좀 어떻게 해줘"),
]


async def _astream_ms(orch, msg):
    """astream 전체(한 번의 라우팅 홉 + 실행 + 직렬화) = 진짜 E2E."""
    t = time.perf_counter()
    async for _ in orch.astream(msg):
        pass
    return (time.perf_counter() - t) * 1000


async def _aroute_ms(orch, msg):
    t = time.perf_counter()
    plan = await orch.aroute(msg)
    return (time.perf_counter() - t) * 1000, plan.capabilities


def part_b_timing(rounds=6):
    print("=" * 72)
    print(f"실측 타이밍 (구간별/총, {rounds}회 중앙값, ms)")
    print("=" * 72)
    llm = os.getenv("LLM_BACKED", "").lower() in ("1", "true", "yes", "on")
    if not llm:
        print("  ⚠️  LLM_BACKED 미설정 — 결정적 경로만 측정(LLM 홉 0).")

    from app.orchestrator.planner import LLMPlanner
    planner = LLMPlanner() if llm else None
    cap_llm = CapabilityOrchestrator(llm_planner=planner)
    cap_det = CapabilityOrchestrator(llm_planner=None)

    loop = asyncio.new_event_loop()
    md = statistics.median
    for label, msg in TIMING_CORPUS:
        e2e, hop, det, plan = [], [], [], None
        for _ in range(rounds):
            e2e.append(loop.run_until_complete(_astream_ms(cap_llm, msg)))         # E2E(1홉+실행)
            h, plan = loop.run_until_complete(_aroute_ms(cap_llm, msg))
            hop.append(h)                                                          # 홉 단독
            det.append(loop.run_until_complete(_astream_ms(cap_det, msg)))         # 실행+스트림(결정적)
        print(f"\n  [{label}] {msg[:44]}  → plan={plan}")
        print(f"    · ① LLM 라우팅 홉(apropose)   : {md(hop):7.1f}  (min {min(hop):.0f} / max {max(hop):.0f})")
        print(f"    · ② capability 실행+스트림    : {md(det):7.3f}  ← 결정적, 홉 무관")
        print("    · ────────────────────────────────────────")
        print(f"    · 실 총 E2E(astream)          : {md(e2e):7.1f}  (min {min(e2e):.0f} / max {max(e2e):.0f})")
        print(f"    · 홉 비중                      : {md(hop)/md(e2e)*100:6.1f}%")
    loop.close()


if __name__ == "__main__":
    part_b_timing()

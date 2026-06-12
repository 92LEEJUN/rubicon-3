"""E2E 패리티 + 실측 타이밍 — (c) 스트랭글러 마무리 근거 + (a) 구간별/총 시간.

Part A (패리티, LLM 없음): core.Orchestrator.stream_turn 와
        CapabilityOrchestrator(planner=None).stream_turn 의 §2.1 봉투를 코퍼스로 비교.
        100% 동일하면 core 경로를 capability 결정적 경로로 수렴(=core 제거) 안전.
Part B (실측 타이밍, 실 LLM): CAPABILITY_ORCH 경로의 구간별/총 시간.
        - 결정적 총(LLM 없음): classify+caps+stream 베이스라인
        - LLM 홉(apropose) 단독: 라우팅 1홉
        - 실 총(LLM 플래너): 전체

실행: cd backend && LLM_BACKED=1 python verify_e2e_timing.py
"""
import asyncio
import os
import statistics
import time

from app.orchestrator.core import Orchestrator
from app.orchestrator.capability import CapabilityOrchestrator, advisory_catalog

PARITY_CORPUS = [
    "세탁기에서 물이 안 빠져요",
    "공기청정기 신제품 추천해줘",
    "배수필터 주문해줘",
    "냉장고 상태 어때?",
    "안녕하세요",
    "세탁기 5C 에러 해결법 알려주고 배수필터도 주문해줘",
]

TIMING_CORPUS = [
    ("clean 단일", "세탁기에서 물이 안 빠져요"),
    ("F2 보증/예약", "보증으로 무상 수리 되는지랑 기사 방문 예약도 가능한가요"),
    ("모호", "이거 좀 어떻게 해줘"),
]


def _strip(chunks):
    """비교용 정규화 — message_id(uuid) 같은 비결정 필드 제거."""
    out = []
    for c in chunks:
        c = dict(c)
        c.pop("message_id", None)
        out.append(c)
    return out


def part_a_parity():
    print("=" * 72)
    print("PART A — 결정적 패리티 (core ≡ capability planner=None)")
    print("=" * 72)
    core = Orchestrator()
    cap = CapabilityOrchestrator(llm_planner=None)
    allmatch = True
    for msg in PARITY_CORPUS:
        a = _strip(list(core.stream_turn(msg)))
        b = _strip(list(cap.stream_turn(msg)))
        ok = a == b
        allmatch &= ok
        mark = "✅ 동일" if ok else "❌ 차이"
        print(f"  {mark}  {msg[:38]}")
        if not ok:
            ta = [x.get("type") for x in a]
            tb = [x.get("type") for x in b]
            print(f"      core={ta}\n      cap ={tb}")
            # 섹션 intent 비교
            sa = [x.get("section", {}).get("intent") for x in a if x.get("type") == "section"]
            sb = [x.get("section", {}).get("intent") for x in b if x.get("type") == "section"]
            print(f"      core intents={sa}  cap intents={sb}")
    print(f"\n  → 전체 패리티: {'✅ 100% 동일 (core 수렴 안전)' if allmatch else '❌ 차이 있음 (core 유지)'}")
    return allmatch


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
    print("\n" + "=" * 72)
    print(f"PART B — 실측 타이밍 (구간별/총, {rounds}회 중앙값, ms)")
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
            e2e.append(loop.run_until_complete(_astream_ms(cap_llm, msg)))        # E2E(1홉+실행)
            h, plan = loop.run_until_complete(_aroute_ms(cap_llm, msg)); hop.append(h)  # 홉 단독
            det.append(loop.run_until_complete(_astream_ms(cap_det, msg)))        # 실행+스트림(결정적)
        print(f"\n  [{label}] {msg[:44]}  → plan={plan}")
        print(f"    · ① LLM 라우팅 홉(apropose)   : {md(hop):7.1f}  (min {min(hop):.0f} / max {max(hop):.0f})")
        print(f"    · ② capability 실행+스트림    : {md(det):7.3f}  ← 결정적, 홉 무관")
        print(f"    · ────────────────────────────────────────")
        print(f"    · 실 총 E2E(astream)          : {md(e2e):7.1f}  (min {min(e2e):.0f} / max {max(e2e):.0f})")
        print(f"    · 홉 비중                      : {md(hop)/md(e2e)*100:6.1f}%")
    loop.close()


if __name__ == "__main__":
    part_a_parity()
    part_b_timing()

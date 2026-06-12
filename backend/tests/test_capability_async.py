"""capability 오케스트레이터 비동기 경로(§9.2) — aroute/astream 결정적 검증.

레포에 pytest-asyncio가 없으므로(test_runtime.py와 동일) asyncio.run으로 코루틴/
비동기 제너레이터를 구동한다. LLM 호출은 stub 플래너로 대체해 네트워크 없이 결정적.
"""
import asyncio

from app.orchestrator.capability import CapabilityOrchestrator, Plan
from app.orchestrator.classify import RuleBasedClassifier


# ── stub 플래너 ──────────────────────────────────────────────────────────────
class _AsyncStub:
    """apropose 코루틴으로 고정 Plan을 반환(비동기 경로 검증)."""

    def __init__(self, caps):
        self.caps = caps
        self.calls = 0

    async def apropose(self, catalog, message):
        self.calls += 1
        return Plan(capabilities=list(self.caps))


class _SyncOnlyStub:
    """propose(sync)만 가진 플래너 — apropose 없음 → aroute는 sync route로 폴백."""

    def __init__(self, caps):
        self.caps = caps
        self.sync_calls = 0

    def propose(self, catalog, message):
        self.sync_calls += 1
        return Plan(capabilities=list(self.caps))


class _AsyncBoom:
    """apropose가 예외 → aroute는 규칙 plan으로 폴백."""

    async def apropose(self, catalog, message):
        raise RuntimeError("planner down")


def _orch(container, planner=None):
    return CapabilityOrchestrator(container=container, classifier=RuleBasedClassifier(),
                                  llm_planner=planner)


async def _collect(agen):
    return [c async for c in agen]


# ── astream 봉투 패리티(요구사항 13) ────────────────────────────────────────
def test_astream_emits_section_flow_done(container):
    stub = _AsyncStub(["diagnose"])
    orch = _orch(container, stub)
    chunks = asyncio.run(_collect(orch.astream("세탁기 물이 안 빠져요")))
    types = [c["type"] for c in chunks]
    assert "section" in types
    assert types[-2] == "flow"
    assert types[-1] == "done"
    assert stub.calls == 1                          # 비동기 플래너 경유


def test_astream_section_before_flow_done(container):
    # 순서: section* → flow → done (모든 section이 flow/done 앞에)
    orch = _orch(container, _AsyncStub(["diagnose"]))
    chunks = asyncio.run(_collect(orch.astream("세탁기 물이 안 빠져요")))
    flow_idx = next(i for i, c in enumerate(chunks) if c["type"] == "flow")
    section_idxs = [i for i, c in enumerate(chunks) if c["type"] == "section"]
    assert section_idxs and all(i < flow_idx for i in section_idxs)
    assert chunks[-1]["type"] == "done" and chunks[-1]["message_id"].startswith("msg_")


def test_astream_error_fallback(container):
    # aroute/실행 중 예외 → error 봉투(stream_turn과 동일 shape), 중단 없이 1청크
    orch = _orch(container)

    async def boom(message):
        raise RuntimeError("route down")

    orch.aroute = boom   # type: ignore[assignment]
    chunks = asyncio.run(_collect(orch.astream("아무거나")))
    assert len(chunks) == 1
    assert chunks[0]["type"] == "error"
    assert chunks[0]["code"] == "orchestrator_error"
    assert chunks[0]["fallback"]["kind"] == "text"


# ── aroute: 비동기 플래너 결과 + 명시 행동 병합 ──────────────────────────────
def test_aroute_uses_apropose_result(container):
    stub = _AsyncStub(["warranty", "booking"])
    orch = _orch(container, stub)
    plan = asyncio.run(orch.aroute("보증 되는지랑 기사 방문 예약 가능한가요"))
    assert plan.capabilities == ["warranty", "booking"]
    assert stub.calls == 1


def test_aroute_preserves_explicit_action(container):
    # LLM 조언형(diagnose) + 규칙 행동형(order) 병합, 우선순위 정렬(diagnose < order)
    stub = _AsyncStub(["diagnose"])
    orch = _orch(container, stub)
    plan = asyncio.run(orch.aroute("보증 되는지랑 가격 알려주고 배수필터 주문해줘"))
    assert "diagnose" in plan.capabilities and "order" in plan.capabilities
    assert plan.capabilities.index("diagnose") < plan.capabilities.index("order")


# ── aroute 폴백 ──────────────────────────────────────────────────────────────
def test_aroute_falls_back_when_no_apropose(container):
    # apropose 없는 플래너 → sync route(propose)로 폴백
    stub = _SyncOnlyStub(["recommend"])
    orch = _orch(container, stub)
    plan = asyncio.run(orch.aroute("공기청정기 추천해줘"))
    assert "recommend" in plan.capabilities
    assert stub.sync_calls == 1                     # sync propose 경유


def test_aroute_falls_back_without_planner(container):
    # 플래너 미연결 → 규칙 plan 폴백(오프라인 결정성)
    orch = _orch(container)
    plan = asyncio.run(orch.aroute("세탁기 물이 안 빠져요"))
    assert "diagnose" in plan.capabilities


def test_aroute_falls_back_on_exception(container):
    # apropose 예외 → 규칙 plan 폴백(예외 누출 없음)
    orch = _orch(container, _AsyncBoom())
    plan = asyncio.run(orch.aroute("세탁기 물이 안 빠져요"))
    assert isinstance(plan.capabilities, list)
    assert "diagnose" in plan.capabilities


# ── 크로스턴 carry — astream도 sync build_turn과 동일 세션 동작 ─────────────
def test_astream_cross_turn_carry(container):
    orch = _orch(container, _AsyncStub(["diagnose"]))
    asyncio.run(_collect(orch.astream("세탁기에서 물이 안 빠져요", session_id="sY")))
    # 명시 order는 규칙 plan에서 병합되어 carry된 required_parts를 이어받는다
    chunks = asyncio.run(_collect(orch.astream("아까 그 부품 주문해줘", session_id="sY")))
    sections = [c["section"] for c in chunks if c["type"] == "section"]
    card = next((s for s in sections if s["template"]["kind"] == "product_card"), None)
    assert card is not None and card["template"]["data"]["id"] == "part_drain_filter"

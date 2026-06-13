"""capability 오케스트레이터 — 조언형/행동형 분리 + CTA 브릿지(ADR-0046).

core.Orchestrator(결정적 백본)를 capability 레지스트리로 감싼 1차 골격이다. 본 모듈은
**결정적**(LLM 없음)이며, 기존 handlers를 재사용해 "LLM 전부 off = 기존 봉투 동일"
회귀를 유지한다(요구사항 13). LLM 플래너/agent capability는 후속 단계에서 얹는다.

핵심(ADR-0046):
- 조언형(diagnose·recommend·status·general) = 정보 + CTA. 자유텍스트에서 자동 선택.
- 행동(order) = 초안(product_card)+확정 CTA만 산출, 커밋은 ActionGate(R17). 모호 질의에서
  자동 선택되지 않는다(명시 의도일 때만).
- 수리 CTA 게이팅: 안전 위험(danger)·보증 무상(coverage=free)이면 부품 자가주문 CTA를
  숨기고 상담원/수리기사 CTA만 + 이유 설명(요구사항 6-3).
- 턴 스코프 + 세션 블랙보드로 required_parts/candidates를 다음 턴 주문이 이어받는다(요구사항 5).
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Iterator, Literal, Optional

from ..container import Container, build_container
from ..domain import AssistantTurn, Cta, MessageSection, Template
from . import handlers
from .classify import IntentClassifier, RuleBasedClassifier

# 우선순위(core._PRIORITY와 동일) — 안전/CS 먼저, 주문은 뒤
_PRIORITY = {"device_status": 0, "troubleshoot": 1, "general": 2, "recommend": 3, "order": 4}
_PLAN_CACHE_MAX = 1024   # route 캐시 경계(메시지→조언형 plan)
_SESSION_MAX = 4096      # 인메모리 세션 경계(멀티유저 누수 방지, ADR-0049)

CapClass = Literal["advisory", "action"]


# ── 턴 스코프 + 세션 블랙보드 ────────────────────────────────────────────────
class TurnCtx:
    """이번 턴 슬롯(turn) + 세션 지속 슬롯(session)을 함께 보는 블랙보드(요구사항 5).

    read는 turn 우선, 없으면 session으로 폴백한다. 이로써 이전 턴 diagnose의
    required_parts를 다음 턴 order가 이어받는다(크로스턴 carry).
    """

    def __init__(self, container: Container, session: dict, user=None) -> None:
        self.c = container
        self.session = session
        self.turn: dict = {}
        self.user = user if user is not None else container.user   # 이 턴의 Principal 사용자(멀티테넌트)

    def write(self, key: str, value) -> None:
        self.turn[key] = value

    def read(self, key: str, default=None):
        if key in self.turn:
            return self.turn[key]
        return self.session.get(key, default)


# ── capability 정의 ──────────────────────────────────────────────────────────
CapabilityFn = Callable[[TurnCtx, str], list[MessageSection]]


@dataclass(frozen=True)
class Capability:
    name: str
    cls: CapClass                       # advisory=플래너 자동선택 가능 / action=명시·CTA만
    kind: Literal["agent", "tool"]
    intents: tuple[str, ...]
    run: CapabilityFn
    emits: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    priority: int = 2
    desc: str = ""                      # LLM 플래너 프롬프트용 한 줄 설명


# ── 수리 CTA 게이팅(요구사항 6·7) ───────────────────────────────────────────
def _cta_connect_agent() -> Cta:
    return Cta(label="상담원 연결", action="chat", kind="handoff")


def _cta_request_visit() -> Cta:
    return Cta(label="수리기사 방문", action="chat", kind="booking", payload={"visit_type": "REPAIR"})


def _cta_explore_replacement() -> Cta:
    # 중립 '교체 알아보기' — 판단은 사용자(요구사항 7). 판매 푸시 아님.
    return Cta(label="교체 모델 알아보기", action="chat", kind="recommend",
               payload={"reason": "uneconomical"})


# 안전 위험 표지(메시지 레벨) — 해결책 데이터가 없어도 위험을 잡는다(요구사항 6-3 보강).
# 장문 검증에서 '해결책 못 찾는 기기(인덕션 등)의 위험 발화'가 게이팅을 빠져나가는 갭을 막는다.
_DANGER_KW = (
    "타는 냄새", "탄내", "타는 듯", "가스 냄새", "가스냄새", "가스", "감전", "스파크",
    "불꽃", "연기", "누전", "폭발", "화재", "쇼트", "스파지",
)


def detect_danger(message: str) -> bool:
    t = message or ""
    return any(k in t for k in _DANGER_KW)


def gate_repair_ctas(section: MessageSection, ctx: TurnCtx, message_danger: bool = False) -> None:
    """guide_steps 섹션의 CTA를 위험도·보증으로 게이팅(결정적, 요구사항 6-3).

    - danger(step.safety 또는 메시지 표지) 또는 coverage=free(보증 무상) → 부품 자가주문 CTA
      숨김 + 이유 설명.
    - 그 외 단순·안전건 → add_to_cart CTA 포함(커밋은 ActionGate).
    - 항상 상담원·수리기사 CTA 제공(요구사항 6-2).
    """
    data = section.template.data
    steps = data.get("steps") or []
    coverage = data.get("coverage")
    required_parts = data.get("required_parts") or []

    step_danger = any(s.get("safety") == "danger" for s in steps)
    risk_level = "danger" if (step_danger or message_danger) else (
        "caution" if any(s.get("safety") == "caution" for s in steps) else "none")
    in_warranty = coverage == "free"

    # 블랙보드 write — 의존 capability·리뷰·다음 턴이 이어받음(요구사항 5)
    ctx.write("risk_level", risk_level)
    ctx.write("warranty_status", "in_warranty" if in_warranty else coverage)
    if required_parts:
        ctx.write("required_parts", required_parts)

    hide_part_cta = risk_level == "danger" or in_warranty
    ctas: list[Cta] = []
    if required_parts and not hide_part_cta:
        ctas.append(handlers._order_cta(required_parts))   # 카드 표시 시점 CTA 동봉(요구사항 3-5)
    ctas.append(_cta_connect_agent())
    ctas.append(_cta_request_visit())

    notice: Optional[str] = None
    if risk_level == "danger":
        notice = ("이 증상은 직접 수리가 위험할 수 있어요. 부품을 직접 구매하기보다 "
                  "상담원·수리기사 방문으로 전문 점검을 받으시길 권해요.")
    elif in_warranty:
        notice = ("보증 기간 내 무상 수리 대상이에요. 부품을 직접 구매하기보다 "
                  "보증 수리(상담원·방문)를 이용하시는 걸 권해요.")
    if notice:
        data["cta_notice"] = notice   # 버튼 숨김 이유 설명(요구사항 6-3)

    section.ctas = ctas


# ── capability 구현(기존 handlers 재사용) ──────────────────────────────────
def _cap_device_status(ctx: TurnCtx, message: str) -> list[MessageSection]:
    sections = handlers.handle_device_status(ctx.c, ctx.user, message)
    for s in sections:
        if s.handled:
            ctx.write("device_status", s.template.data.get("device"))
    return sections


def _cap_diagnose(ctx: TurnCtx, message: str) -> list[MessageSection]:
    sections = handlers.handle_troubleshoot(ctx.c, ctx.user, message)
    danger = detect_danger(message)
    for s in sections:
        if s.template.kind == "guide_steps":
            gate_repair_ctas(s, ctx, message_danger=danger)
        elif danger:
            # 해결책을 못 찾았어도 위험 발화면 안전 경고로 응답(게이팅, 요구사항 6-3).
            ctx.write("risk_level", "danger")
            s.handled = True
            s.template.data["cta_notice"] = (
                "말씀하신 증상은 안전 위험이 있을 수 있어요. 사용을 멈추고 전원(또는 가스)을 "
                "차단한 뒤, 직접 손대기보다 상담원·수리기사 방문으로 점검받으시길 권해요.")
            s.ctas = [_cta_connect_agent(), _cta_request_visit()]
    return sections


def _cap_recommend(ctx: TurnCtx, message: str) -> list[MessageSection]:
    sections = handlers.handle_recommend(ctx.c, ctx.user, message)
    for s in sections:
        prods = s.template.data.get("products") if s.handled else None
        if prods:
            ctx.write("candidates", [p.get("id") for p in prods])
    return sections


def _cap_order(ctx: TurnCtx, message: str) -> list[MessageSection]:
    # 명시 부품이 없으면 블랙보드(이전 턴 진단의 required_parts)를 이어받음(요구사항 5-3)
    ids = handlers.resolve_part_ids(message) or ctx.read("required_parts") or []
    return handlers.handle_order(ctx.c, ctx.user, message, part_ids=ids)


def _cap_general(ctx: TurnCtx, message: str) -> list[MessageSection]:
    return handlers.handle_general(ctx.c, ctx.user, message)


def _cap_warranty(ctx: TurnCtx, message: str) -> list[MessageSection]:
    sections = handlers.handle_warranty(ctx.c, ctx.user, message)
    for s in sections:
        ctx.write("warranty_status", s.template.data.get("coverage"))
    return sections


def _cap_booking(ctx: TurnCtx, message: str) -> list[MessageSection]:
    return handlers.handle_booking(ctx.c, ctx.user, message)


def _cap_explain(ctx: TurnCtx, message: str) -> list[MessageSection]:
    # 직전 추천 후보(blackboard)를 이어받아 상세/비교 설명(요구사항 5)
    return handlers.handle_explain(ctx.c, ctx.user, message, candidates=ctx.read("candidates"))


def _cap_clarify(ctx: TurnCtx, message: str) -> list[MessageSection]:
    return handlers.handle_clarify(ctx.c, ctx.user, message)


# ── F4: 범위 밖/미충족 의도 명시(요구사항 R7) ───────────────────────────────
# 범위 밖 판정은 **LLM 플래너**가 한다(키워드 누락이 많아 폐기). 플래너가 out_of_scope 토픽을
# 내면(Plan.out_of_scope) 침묵 대신 낮은 톤의 안내를 덧붙인다. 플래너 미연결(규칙 폴백)이면
# 신호가 없으므로 out_of_scope를 띄우지 않는다(test-findings F4 처방 — LLM 결정).
def out_of_scope_section(labels: list[str]) -> MessageSection:
    """범위 밖 요청에 대한 낮은 톤의 명시적 미처리(unhandled) 섹션(R7).

    예: "그 외 요청(예: 날씨)은 제가 도와드리기 어려워요." handled=False로 표면화한다.
    """
    examples = ", ".join(labels[:3]) if labels else "일부 요청"
    return MessageSection(
        label="안내", intent="out_of_scope", handled=False,
        template=Template(kind="text", data={
            "message": (f"그 외 요청(예: {examples})은 제가 도와드리기 어려워요. "
                        "가전 상태 점검·문제 해결·부품 주문·추천은 도와드릴 수 있어요."),
            "topics": labels}))


# ── §8~11: LLM 자연어(prose) agent capability — BOUNDED scaffold ─────────────
def _env_on(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def llm_backed() -> bool:
    """LLM_BACKED 토글(매 호출 평가, 기본 off). prose capability의 게이트."""
    return _env_on("LLM_BACKED")


_PROSE_SYSTEM = (
    "당신은 삼성 가전 AI 컨시어지입니다. 사용자에게 친절하고 간결한 한국어로, "
    "추천 제품의 특징(소음·필터·관리 편의 등)을 자연스러운 문장으로 설명하세요. "
    "과장·허위 없이 주어진 제품 정보 범위 안에서만 말합니다."
)


def _prose_fallback(ctx: TurnCtx, message: str) -> list[MessageSection]:
    """LLM off(또는 prose 클라이언트 미주입) 시 결정적 폴백 — 기존 explain 동작 그대로(회귀 불변)."""
    return handlers.handle_explain(ctx.c, ctx.user, message, candidates=ctx.read("candidates"))


def _prose_prompt(items, message: str) -> str:
    lines = []
    for it in items:
        p = it.product
        lines.append(f"- {p.name}: {getattr(p, 'summary', '') or it.reason}")
    catalog = "\n".join(lines) or "(제품 정보 없음)"
    return f"제품 정보:\n{catalog}\n\n사용자 질문:\n{message}"


def _cap_explain_prose(ctx: TurnCtx, message: str) -> list[MessageSection]:
    """§8~11 entry point — kind:"agent" prose capability.

    이 capability는 §8~11(LLM 자연어 prose 응답)의 **첫 진입점(scaffold)**이다.
    전체 prose 마이그레이션과 legacy/runtime 제거는 후속 작업이다(여기선 하지 않는다).

    동작:
    - LLM_BACKED on **그리고** prose 클라이언트가 주입돼 있으면 → LLM이 자연어 text 섹션 생성.
    - 그 외(off·미주입·예외) → 결정적 폴백(_prose_fallback = 기존 explain). 기본 테스트는 결정적.

    prose 클라이언트는 ctx.c.prose_client가 아니라 오케스트레이터가 ctx.turn에 주입한다(아래 참조).
    동기 capability 계약(handler는 sync)을 깨지 않기 위해, 비동기 LLM 호출은 prose 클라이언트의
    동기 어댑터(`complete`)로 감싼다. 실 품질은 수동 검증(verify_*); 테스트는 stub을 쓴다.
    """
    client = ctx.read("_prose_client")
    if not (llm_backed() and client is not None):
        return _prose_fallback(ctx, message)

    items = ctx.c.recommendation.recommend(ctx.user)
    cand = set(ctx.read("candidates") or [])
    chosen = [it for it in items if (not cand or it.product.id in cand)]
    if not chosen:
        return _prose_fallback(ctx, message)

    try:
        text = client.complete(_PROSE_SYSTEM, _prose_prompt(chosen, message))
    except Exception:
        # prose 생성 실패 → 결정적 폴백(침묵·턴 붕괴 방지, §13.1)
        return _prose_fallback(ctx, message)
    if not text:
        return _prose_fallback(ctx, message)
    return [MessageSection(
        label=handlers.LABELS.get("explain", "상세 설명"), intent="explain",
        template=Template(kind="text", data={
            "message": text,
            "prose": True,
            "products": [{"id": it.product.id} for it in chosen]}))]


def build_registry() -> dict[str, Capability]:
    caps = [
        Capability("device_status", "advisory", "tool", ("device_status",), _cap_device_status,
                   emits=("device_status",), priority=0,
                   desc="기기의 '현재 상태/이상 여부'를 조회(연결·소모품·이상 신호)."),
        Capability("diagnose", "advisory", "tool", ("troubleshoot",), _cap_diagnose,
                   emits=("required_parts", "risk_level", "warranty_status"), priority=1,
                   desc="고장·증상·에러코드의 원인 진단 + 자가 해결 가이드 + 안전/부품 안내."),
        Capability("warranty", "advisory", "tool", ("warranty",), _cap_warranty,
                   emits=("warranty_status",), priority=1,
                   desc="보증(유·무상) 여부 안내. '보증 되나요/무상 수리' 류."),
        Capability("explain", "advisory", "tool", ("explain",), _cap_explain,
                   needs=("candidates",), priority=2,
                   desc="제품/추천의 스펙·가격·소음·비교 등 상세 설명. '더 알려줘/비교/얼마' 류."),
        Capability("booking", "advisory", "tool", ("booking",), _cap_booking, priority=2,
                   desc="방문 예약 가능 시간 안내(초안). '기사 예약/방문' 류. 커밋은 확정 CTA."),
        Capability("general", "advisory", "tool", ("general",), _cap_general, priority=2,
                   desc="일반 안내. 위 어디에도 안 맞는 단순 인사·범위 안내."),
        Capability("clarify", "advisory", "tool", ("clarify",), _cap_clarify, priority=2,
                   desc="요청이 모호하거나 무엇을 원하는지 불명확할 때 되묻기."),
        Capability("recommend", "advisory", "tool", ("recommend",), _cap_recommend,
                   emits=("candidates",), priority=3,
                   desc="새 제품 추천(개인화). '추천해줘/뭐가 좋아/새로 장만' 류."),
        # §8~11 — LLM 자연어(prose) agent capability(scaffold). kind="agent"로 결정적 tool과 구분.
        # LLM_BACKED on + prose 클라이언트 주입 시 자연어 text, 아니면 결정적 explain 폴백(기본).
        Capability("explain_prose", "advisory", "agent", ("explain_prose",), _cap_explain_prose,
                   needs=("candidates",), priority=2,
                   desc="제품/추천을 LLM 자연어 문장으로 설명(§8~11). off면 결정적 explain."),
        # 행동형 — 플래너 자동선택 제외. 명시 order 의도 또는 CTA 회신으로만 진입. 초안만 산출.
        Capability("order", "action", "tool", ("order",), _cap_order,
                   needs=("required_parts",), priority=4,
                   desc="부품/제품 주문 초안(커밋은 CTA 확정). 플래너 자동선택 금지."),
    ]
    return {c.name: c for c in caps}


def advisory_catalog(registry: dict[str, Capability]) -> list[Capability]:
    """플래너 후보 = 조언형만(요구사항 1-3·4-1)."""
    return [c for c in registry.values() if c.cls == "advisory"]


# ── 플래너(룰) + 검증 ────────────────────────────────────────────────────────
@dataclass
class Plan:
    capabilities: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)   # LLM이 판정한 범위 밖 토픽(F4)


def rule_plan(intents: list[str], registry: dict[str, Capability]) -> Plan:
    """분류된 의도를 capability로 매핑(우선순위 정렬). 행동형은 **명시 의도일 때만** 포함."""
    by_intent = {i: name for name, cap in registry.items() for i in cap.intents}
    names: list[str] = []
    for intent in intents:
        name = by_intent.get(intent)
        if name and name not in names:
            names.append(name)
    names.sort(key=lambda n: registry[n].priority)
    return Plan(capabilities=names)


def validate_plan(plan: Plan, intents: list[str], registry: dict[str, Capability]) -> Plan:
    """행동형 capability는 해당 의도가 명시 분류됐을 때만 허용(자동선택 차단, 요구사항 4-2)."""
    explicit = set(intents)
    kept: list[str] = []
    for name in plan.capabilities:
        cap = registry.get(name)
        if cap is None:
            continue
        if cap.cls == "action" and not (set(cap.intents) & explicit):
            continue   # 행동형 자동선택 차단
        kept.append(name)
    return Plan(capabilities=kept)


# ── 오케스트레이터 ───────────────────────────────────────────────────────────
class CapabilityOrchestrator:
    """capability 레지스트리 기반 오케스트레이터(ADR-0043·0046·0048).

    **LLM 플래너를 모든 질의의 단일 라우터로** 둔다(ADR-0048, 게이트 폐기). 규칙 분류기는
    LLM 플래너 미연결·실패 시의 폴백으로만 쓴다. core.Orchestrator와 동일한 §2.1 봉투를
    내며, 세션 블랙보드로 멀티턴 carry를 지원한다.
    """

    def __init__(self, container: Optional[Container] = None,
                 classifier: Optional[IntentClassifier] = None,
                 llm_planner=None, prose_client=None) -> None:
        self.c = container or build_container()
        self.classifier = classifier or RuleBasedClassifier()
        self.registry = build_registry()
        self._sessions: dict[str, dict] = {}   # session_id → 지속 슬롯
        self.llm_planner = llm_planner          # 단일 라우터(없으면 규칙 폴백)
        # §8~11 prose 클라이언트(주입형) — complete(system, user)->str. 없으면 prose capability는
        # 결정적 폴백(explain)으로 동작한다. 기본 None → 테스트·오프라인 결정성 유지.
        self.prose_client = prose_client
        # message → (조언형 plan, out_of_scope 토픽). 홉 생략(§9.2).
        self._plan_cache: dict[str, tuple[list[str], list[str]]] = {}

    def _ordered_intents(self, message: str) -> list[str]:
        result = self.classifier.classify(message)
        return sorted(result.intents, key=lambda i: _PRIORITY.get(i, 9))

    def plan(self, message: str) -> Plan:
        """규칙 폴백 plan — LLM 플래너 미연결·실패 시에만 사용."""
        intents = self._ordered_intents(message)
        return validate_plan(rule_plan(intents, self.registry), intents, self.registry)

    def _merge_advisory_actions(self, advisory: list[str], rule: Plan) -> list[str]:
        """LLM 조언형 + 규칙 plan의 명시 행동(order)을 우선순위 정렬로 병합(route/aroute 공통)."""
        actions = [n for n in rule.capabilities if self.registry[n].cls == "action"]
        names = advisory + [a for a in actions if a not in advisory]
        names.sort(key=lambda n: self.registry[n].priority)
        return names

    def _cache_get(self, message: str):
        """캐시된 (조언형 plan, out_of_scope)(없으면 None). route는 메시지의 순수 함수(§9.2)."""
        return self._plan_cache.get(message)

    def _cache_put(self, message: str, advisory: list[str], oos: list[str]) -> None:
        if len(self._plan_cache) >= _PLAN_CACHE_MAX:      # 단순 FIFO 경계
            self._plan_cache.pop(next(iter(self._plan_cache)))
        self._plan_cache[message] = (advisory, oos)

    def _route_with(self, message: str, rule: Plan, advisory, oos: list[str]) -> Plan:
        """LLM 결과(advisory + out_of_scope)를 규칙 행동과 병합해 최종 Plan을 만든다(route/aroute 공통)."""
        if advisory:
            names = self._merge_advisory_actions(advisory, rule)
            if names:
                return Plan(capabilities=names, out_of_scope=oos)
        if oos:   # 범위 밖만 있고 고를 capability가 없음 → 규칙 plan + out_of_scope
            return Plan(capabilities=rule.capabilities, out_of_scope=oos)
        return rule

    def route(self, message: str) -> Plan:
        """**모든 질의를 LLM 플래너로 라우팅**(ADR-0048). LLM은 조언형 + 범위 밖(out_of_scope)을 내고,
        명시 행동(order)은 규칙 plan에서 보존·병합한다. 동일 메시지는 캐시로 홉 생략(§9.2). 플래너
        미연결·실패·빈 결과면 규칙 plan으로 폴백(요구사항 14-2)."""
        rule = self.plan(message)
        if self.llm_planner is not None:
            cached = self._cache_get(message)
            if cached is None:
                try:
                    intents = self._ordered_intents(message)
                    proposed = self.llm_planner.propose(advisory_catalog(self.registry), message)
                    advisory = validate_plan(proposed, intents, self.registry).capabilities
                    oos = list(getattr(proposed, "out_of_scope", []) or [])
                    self._cache_put(message, advisory, oos)
                except Exception:
                    advisory, oos = None, []   # 플래너 실패 → 캐시 안 함, 규칙 폴백
            else:
                advisory, oos = cached
            return self._route_with(message, rule, advisory, oos)
        return rule

    async def aroute(self, message: str) -> Plan:
        """route()의 비동기 버전 — 플래너에 apropose 코루틴이 있으면 await로 라우팅(ADR-0048).

        병합·캐시·out_of_scope 로직은 sync route()와 동일. apropose가 없거나 예외면 route()로 폴백."""
        if self.llm_planner is not None and hasattr(self.llm_planner, "apropose"):
            rule = self.plan(message)
            cached = self._cache_get(message)
            if cached is None:
                try:
                    intents = self._ordered_intents(message)
                    proposed = await self.llm_planner.apropose(advisory_catalog(self.registry), message)
                    advisory = validate_plan(proposed, intents, self.registry).capabilities
                    oos = list(getattr(proposed, "out_of_scope", []) or [])
                    self._cache_put(message, advisory, oos)
                except Exception:
                    advisory, oos = None, []
            else:
                advisory, oos = cached
            return self._route_with(message, rule, advisory, oos)
        # apropose 없음(또는 플래너 미연결) → sync route(propose/규칙 폴백)로 위임
        return self.route(message)

    def _run_capabilities(self, plan: Plan, ctx: TurnCtx, message: str,
                          session: dict) -> list[MessageSection]:
        """plan의 capability를 순차 실행하고 세션 carry를 갱신한다(build_turn/astream 공통).

        capability handler는 동기(결정적)이므로 그대로 호출한다. 각 capability는 **독립 폴백**으로
        감싸 한 step 실패가 턴 전체를 무너뜨리지 않게 한다(요구사항 14·§13.1). 산출 섹션이 하나도
        없으면(빈 plan·전부 실패) 침묵 대신 clarify로 되묻는다(R7 — 빈 턴 금지, F4 보강)."""
        sections: list[MessageSection] = []
        for name in plan.capabilities:
            try:
                sections.extend(self.registry[name].run(ctx, message))
            except Exception as exc:   # 실패 step만 폴백 — 나머지 capability는 계속(§13.1)
                sections.append(MessageSection(
                    label=handlers.LABELS.get(name, "안내"), intent=name, handled=False,
                    template=Template(kind="text", data={
                        "message": "이 요청을 처리하는 중 일시적인 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
                        "detail": str(exc)})))

        if not sections:   # 빈 턴 방지(R7) — 무엇을 원하는지 되묻기
            sections = handlers.handle_clarify(ctx.c, ctx.user, message)

        # F4(R7) — 플래너가 범위 밖 요청(plan.out_of_scope)을 판정하면 침묵 대신 명시적 미처리 안내.
        # clarify로만 응답한 경우(전부 미해석)는 이미 되묻기이므로 중복 안내하지 않는다.
        oos = list(getattr(plan, "out_of_scope", []) or [])
        already_only_clarify = all(s.intent == "clarify" for s in sections)
        if oos and not already_only_clarify:
            sections.append(out_of_scope_section(oos))

        # 세션 carry 갱신 — 다음 턴 주문이 이어받을 슬롯 보존(요구사항 5)
        for slot in ("required_parts", "candidates"):
            if slot in ctx.turn:
                session[slot] = ctx.turn[slot]
        return sections

    def _session(self, session_id: str) -> dict:
        """세션 블랙보드 — 경계(_SESSION_MAX) 초과 시 가장 오래된 세션 evict(멀티유저 누수 방지)."""
        if session_id not in self._sessions and len(self._sessions) >= _SESSION_MAX:
            self._sessions.pop(next(iter(self._sessions)))
        return self._sessions.setdefault(session_id, {})

    def build_turn(self, message: str, session_id: str = "s1",
                   screen_context: Optional[dict] = None, user=None) -> AssistantTurn:
        session = self._session(session_id)
        ctx = TurnCtx(self.c, session, user)   # user=Principal 사용자(None이면 기본, 멀티테넌트)
        ctx.turn["_prose_client"] = self.prose_client   # §8~11 prose capability용(없으면 결정적 폴백)
        plan = self.route(message)

        sections = self._run_capabilities(plan, ctx, message, session)

        active_flow = "troubleshoot" if any(s.intent == "troubleshoot" for s in sections) else None
        return AssistantTurn(sections=sections, active_flow=active_flow,
                             message_id=f"msg_{uuid.uuid4().hex[:8]}")

    def stream_turn(self, message: str, session_id: str = "s1",
                    screen_context: Optional[dict] = None, user=None) -> Iterator[dict]:
        """§2.1 봉투 — section* → flow → done(실패 시 error). core.stream_turn과 동등."""
        try:
            turn = self.build_turn(message, session_id, screen_context, user=user)
        except Exception as exc:   # 전체 폴백(R13)
            yield {"type": "error", "code": "orchestrator_error",
                   "fallback": {"kind": "text",
                                "data": {"message": "일시적인 문제가 발생했어요. 잠시 후 다시 시도해 주세요."}},
                   "detail": str(exc)}
            return
        for section in turn.sections:
            yield {"type": "section", "section": section.model_dump(mode="json")}
        yield {"type": "flow", "active_flow": turn.active_flow}
        yield {"type": "done", "message_id": turn.message_id}

    async def astream(self, message: str, session_id: str = "s1",
                      screen_context: Optional[dict] = None, user=None) -> AsyncIterator[dict]:
        """stream_turn의 비동기 버전 — aroute(LLM-planner)로 플래닝 후 §2.1 봉투를 방출한다.

        section* → flow → done(실패 시 error). sync stream_turn과 동일 봉투·세션 carry.

        한계: 본 구현은 '결정적-섹션-우선 스트리밍'을 capability가 끝나는 즉시 섹션을
        방출하는 수준으로만 한다. 완전한 speculative pre-paint(추정 선-렌더)는 범위 밖이다.
        capability handler는 동기(결정적)이므로 await 없이 그대로 호출한다."""
        try:
            session = self._session(session_id)
            ctx = TurnCtx(self.c, session, user)   # user=Principal 사용자(멀티테넌트)
            ctx.turn["_prose_client"] = self.prose_client   # §8~11 prose capability용
            plan = await self.aroute(message)
            sections = self._run_capabilities(plan, ctx, message, session)
            active_flow = "troubleshoot" if any(
                s.intent == "troubleshoot" for s in sections) else None
            message_id = f"msg_{uuid.uuid4().hex[:8]}"
        except Exception as exc:   # 전체 폴백(R13) — stream_turn과 동일 error 봉투
            yield {"type": "error", "code": "orchestrator_error",
                   "fallback": {"kind": "text",
                                "data": {"message": "일시적인 문제가 발생했어요. 잠시 후 다시 시도해 주세요."}},
                   "detail": str(exc)}
            return
        for section in sections:
            yield {"type": "section", "section": section.model_dump(mode="json")}
        yield {"type": "flow", "active_flow": active_flow}
        yield {"type": "done", "message_id": message_id}

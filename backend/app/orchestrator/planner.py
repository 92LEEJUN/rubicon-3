"""LLM 플래너 = 슈퍼바이저 — 턴의 양끝(plan 분해 + compose 조립)을 담당(ADR-0048·0053).

- **plan(`propose`/`apropose`)**: 모든 질의를 LLM 라우팅 — 조언형 capability + 범위 밖(out_of_scope)을
  구조화 출력(json_schema)으로 고른다. 행동(order)은 여기서 고르지 않는다(사용자가 CTA로 확정).
  실패 시 호출측이 규칙 plan으로 폴백한다.
- **compose(`compose`/`acompose`)**: 핸들러가 만든 섹션 facts를 받아 **자연어 내러티브만** 종합한다
  (ADR-0053). 데이터(카드·CTA·가격·id)는 재생성하지 않고 참조만 한다. 같은 모델·클라이언트 재사용.
"""
from __future__ import annotations

import json
from typing import Optional

from ..llm import MODEL, achat_completion, get_client
from .capability import Capability, Plan
from .prompts import COMPOSER_PROMPT

_SYSTEM = (
    "당신은 삼성 가전 AI 컨시어지의 '플래너'입니다. 사용자 메시지를 처리하려면 어떤 "
    "조언형 capability를 어떤 순서로 실행할지 고르세요. 규칙:\n"
    "1) 반드시 주어진 후보 이름 중에서만 고릅니다(없는 이름 금지).\n"
    "2) '구매 커밋'(주문/결제)은 고르지 않습니다 — 사용자가 CTA로 확정합니다. 단 보증 안내·"
    "예약 가능 시간 안내·상세 설명은 정보 제공이므로 고를 수 있습니다.\n"
    "3) 안전·진단(diagnose)을 먼저, 추천(recommend)을 뒤에 둡니다.\n"
    "4) 한 메시지에 여러 요청이 섞여 있으면 해당하는 capability를 모두 고릅니다.\n"
    "5) 무엇을 원하는지 정말 불명확하면(중의적·정보 부족) clarify 하나만 고릅니다.\n"
    "6) 단순 잡담·범위 밖이면 general만 고릅니다.\n"
    "7) 기기의 '현재 상태'를 묻는 게 아니라 고장·증상·방법을 묻는 거면 device_status가 아니라 "
    "diagnose를 고릅니다. 보증 여부는 warranty, 스펙·가격·비교는 explain을 고릅니다.\n"
    "8) 최소 집합 원칙: 메시지가 명시적으로 요청한 capability만 고릅니다. 메시지의 각 요청 문구를 "
    "그에 대응하는 capability 하나에만 매핑하고, 어떤 요청 문구에도 직접 대응하지 않는 capability는 "
    "절대 추가하지 않습니다. 특히 recommend·general·explain·booking 등은 사용자가 그 행위를 "
    "명시적으로 요청했을 때만 고릅니다(예: '추천'이라는 말이 없으면 recommend 금지, '예약/방문'이라는 "
    "말이 없으면 booking 금지). 추가하면 더 도움이 될 것 같다는 이유로 capability를 덧붙이지 않습니다. "
    "예) '고장 해결법 알려주고 필터도 주문해줘' → diagnose·order만 (recommend·explain·general·booking "
    "넣지 않음). 확신이 없으면 더 적게 고릅니다.\n"
    "9) 범위 밖(out_of_scope): 메시지에 **가전 컨시어지와 무관한 요청**(예: 날씨·기온·미세먼지·뉴스·"
    "주식·환율·운세·번역·맛집·길찾기 등)이 섞여 있으면, 그 주제를 `out_of_scope`에 짧은 한국어 라벨로 "
    "나열합니다(없으면 빈 배열 []). 이 요청들은 capabilities로 처리하지 않습니다. 가전 관련(상태·고장·"
    "부품·추천·보증·예약)은 범위 안이므로 out_of_scope에 넣지 않습니다."
)


def _schema(names: list[str]) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "capability_plan",
            "schema": {
                "type": "object",
                "properties": {
                    "capabilities": {
                        "type": "array",
                        "items": {"type": "string", "enum": names},
                    },
                    "out_of_scope": {
                        "type": "array",
                        "items": {"type": "string"},   # 범위 밖 주제 라벨(자유), 없으면 []
                    },
                },
                "required": ["capabilities", "out_of_scope"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }


def _user_prompt(catalog: list[Capability], message: str) -> str:
    desc = "\n".join(f"- {c.name}: {c.desc or ('의도=' + '/'.join(c.intents))}" for c in catalog)
    return f"capability 후보:\n{desc}\n\n사용자 메시지:\n{message}"


def _parse(content: str, names: list[str]) -> Plan:
    data = json.loads(content)
    picked = [n for n in data.get("capabilities", []) if n in names]
    oos = [str(t) for t in data.get("out_of_scope", []) if isinstance(t, str) and t.strip()]
    return Plan(capabilities=picked, out_of_scope=oos)


def _compose_prompt(message: str, plan: Plan, facts: list[dict]) -> str:
    """compose 사용자 프롬프트 — 섹션 facts 요약 + 원 메시지(데이터 재생성 금지, ADR-0053)."""
    lines = []
    for f in facts:
        brief = f.get("brief") or ""
        lines.append(f"- [{f.get('label', '')}] ({f.get('intent', '')}) {brief}".rstrip())
    block = "\n".join(lines) or "(처리 결과 없음)"
    oos = list(getattr(plan, "out_of_scope", []) or [])
    extra = f"\n\n범위 밖으로 처리하지 못한 요청: {', '.join(oos)}" if oos else ""
    return f"사용자 메시지:\n{message}\n\n처리 결과(facts):\n{block}{extra}"


class LLMPlanner:
    """슈퍼바이저(주입형) — plan(propose/apropose) + compose(compose/acompose). 동기/비동기 제공."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or MODEL

    def propose(self, catalog: list[Capability], message: str) -> Plan:
        names = [c.name for c in catalog]
        resp = get_client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _user_prompt(catalog, message)},
            ],
            response_format=_schema(names),
        )
        return _parse(resp.choices[0].message.content, names)

    async def apropose(self, catalog: list[Capability], message: str) -> Plan:
        names = [c.name for c in catalog]
        resp = await achat_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _user_prompt(catalog, message)},
            ],
            response_format=_schema(names),
        )
        return _parse(resp.choices[0].message.content, names)

    # ── compose(조립) — 섹션 facts → 자연어 내러티브(ADR-0053) ──────────────
    def compose(self, message: str, plan: Plan, facts: list[dict]) -> str:
        resp = get_client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": COMPOSER_PROMPT},
                {"role": "user", "content": _compose_prompt(message, plan, facts)},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    async def acompose(self, message: str, plan: Plan, facts: list[dict]) -> str:
        resp = await achat_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": COMPOSER_PROMPT},
                {"role": "user", "content": _compose_prompt(message, plan, facts)},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

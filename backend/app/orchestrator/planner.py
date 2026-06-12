"""LLM 플래너 — 에스컬레이션된 턴에서 조언형 capability를 동적 선택(ADR-0046·0047, 요구사항 4-1).

규칙 분류기가 부서지는 장문·모호 턴(test-findings F1·F2)에서만 호출된다(티어드, ADR-0047).
구조화 출력(json_schema)으로 **후보(조언형) 이름만** 고르게 강제 — 행동(order·booking)은
여기서 고르지 않는다(사용자가 CTA로 확정). 실패 시 호출측이 규칙 plan으로 폴백한다.
"""
from __future__ import annotations

import json
from typing import Optional

from ..llm import MODEL, achat_completion, get_client
from .capability import Capability, Plan

_SYSTEM = (
    "당신은 삼성 가전 AI 컨시어지의 '플래너'입니다. 사용자 메시지를 처리하려면 어떤 "
    "'조언형 capability'를 어떤 순서로 실행할지 고르세요. 규칙:\n"
    "1) 반드시 주어진 후보 이름 중에서만 고릅니다(없는 이름 금지).\n"
    "2) 주문·예약·결제 같은 '행동'은 고르지 않습니다 — 그건 사용자가 CTA로 직접 확정합니다.\n"
    "3) 안전·진단(diagnose)을 먼저, 추천(recommend)을 뒤에 둡니다.\n"
    "4) 한 메시지에 여러 요청이 섞여 있으면 해당하는 capability를 모두 고릅니다.\n"
    "5) 단순 잡담·범위 밖이면 general만 고릅니다.\n"
    "6) 기기의 '현재 상태'를 묻는 게 아니라 고장·증상·가격·방법을 묻는 거면 "
    "device_status가 아니라 diagnose를 고릅니다."
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
                },
                "required": ["capabilities"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }


def _user_prompt(catalog: list[Capability], message: str) -> str:
    desc = "\n".join(f"- {c.name}: 의도={'/'.join(c.intents)}" for c in catalog)
    return f"capability 후보:\n{desc}\n\n사용자 메시지:\n{message}"


def _parse(content: str, names: list[str]) -> Plan:
    data = json.loads(content)
    picked = [n for n in data.get("capabilities", []) if n in names]
    return Plan(capabilities=picked)


class LLMPlanner:
    """조언형 capability 선택을 LLM 구조화 출력으로 제안(주입형). 동기/비동기 모두 제공."""

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

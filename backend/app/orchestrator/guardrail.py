"""가드레일 에이전트 — 입력(pre)/출력(post) 안전 검사(ADR-0052·0054).

신뢰·안전을 기능 코드에 인라인하지 않고 **한 경계 에이전트**로 모은다. 검사는 **LLM 없이 규칙
(정규식·패턴)으로 결정적** — 단위 검증 가능(ADR-0052 §결정적). 토글(`GUARDRAIL`) off면 미발동
= 오늘과 동일(스트랭글러).

- 입력 검사(pre, `screen`) — 의도 추출과 **병렬**(ADR-0054). 프롬프트 인젝션·탈옥·남용 패턴 탐지.
  차단(block)이면 capability 실행을 스킵하고 안전 거부로 응답. 호출측에서 예외는 **fail-closed**.
- 출력 검사(post, `check`) — 방출 직전. 응답 **텍스트**의 PII(전화·카드·이메일) 마스킹. 구조화
  계약 필드(가격·id 등)는 훼손하지 않는다(텍스트만 대상, ADR-0054).

상세 정책·패턴 확장(레이트리밋·감사 로그 등)은 `specs/trust-safety-baseline/`에서 이 위에 얹는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..domain import MessageSection, Template


@dataclass
class Verdict:
    """가드레일 pre-screen 판정. allowed=False면 차단(fail-closed)."""

    allowed: bool = True
    reason: str = ""                              # 차단 사유(내부·감사용)
    topics: list[str] = field(default_factory=list)
    soften: bool = False                          # 통과하되 어투 완화 힌트(compose 입력)


# ── 입력(pre) 패턴 — 프롬프트 인젝션·탈옥(llm-policy 정합) ────────────────────
# "이전 지시 무시" 류는 사용자 입력이 시스템 정책을 덮어쓰려는 시도. 결정적으로 차단한다.
_INJECTION_PATTERNS = (
    re.compile(r"이전\s*(의|에)?\s*지시\s*(를)?\s*(무시|잊)", re.I),
    re.compile(r"위\s*(의)?\s*(지시|규칙|정책)\s*(을|를)?\s*(무시|무효)", re.I),
    re.compile(r"\bignore\s+(all\s+)?(the\s+)?previous\b", re.I),
    re.compile(r"\bdisregard\s+(all\s+)?(the\s+)?(prior|previous|above)\b", re.I),
    re.compile(r"시스템\s*프롬프트", re.I),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"(개발자|developer)\s*모드", re.I),
    re.compile(r"\b(jailbreak|DAN\s+모드)\b", re.I),
    re.compile(r"너의?\s*(규칙|정책|지침)\s*(을|를)?\s*(알려|말해|노출|보여)", re.I),
)


# ── 출력(post) PII 패턴 — 텍스트만 마스킹 ────────────────────────────────────
_PII_PATTERNS = (
    # 카드번호(13~16자리, 구분자 허용) — 길이가 긴 것부터
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[카드번호 보호됨]"),
    # 한국 휴대전화
    (re.compile(r"\b01[016789][ -]?\d{3,4}[ -]?\d{4}\b"), "[전화번호 보호됨]"),
    # 이메일
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[이메일 보호됨]"),
)


class Guardrail:
    """결정적 안전 가드레일(주입형). LLM 없음 — 규칙 기반(ADR-0052·0054)."""

    def screen(self, message: str) -> Verdict:
        """입력 pre-screen — 인젝션·탈옥 패턴이면 차단(fail-closed는 호출측 예외 처리)."""
        t = message or ""
        for pat in _INJECTION_PATTERNS:
            if pat.search(t):
                return Verdict(allowed=False, reason="prompt_injection",
                               topics=["프롬프트 인젝션 시도"])
        return Verdict(allowed=True)

    async def ascreen(self, message: str) -> Verdict:
        """screen의 비동기 버전 — 라우팅과 gather로 병렬(ADR-0054). 결정적이라 동기 위임."""
        return self.screen(message)

    def _mask_text(self, text: str) -> str:
        out = text
        for pat, repl in _PII_PATTERNS:
            out = pat.sub(repl, out)
        return out

    def check(self, sections: list[MessageSection]) -> list[MessageSection]:
        """출력 post-check — 텍스트형 data.message의 PII만 마스킹(구조 필드 불변, ADR-0054).

        섹션 객체를 in-place 수정한다(호출측은 방출 직전에만 사용). text kind 또는 message 키를
        가진 data만 대상 — 가격·id 등 계약 필드는 건드리지 않는다.
        """
        for s in sections:
            data = s.template.data if s.template else None
            if isinstance(data, dict):
                msg = data.get("message")
                if isinstance(msg, str) and msg:
                    data["message"] = self._mask_text(msg)
        return sections

    def refusal_section(self, verdict: Verdict) -> MessageSection:
        """차단(fail-closed) 시 안전 거부 섹션 — 침묵 대신 낮은 톤으로 사유·가능 범위 안내."""
        return MessageSection(
            label="안내", intent="blocked", handled=False,
            template=Template(kind="text", data={
                "message": ("요청하신 내용은 안전·정책상 도와드리기 어려워요. 가전 상태 점검·문제 해결·"
                            "부품 주문·추천은 도와드릴 수 있어요."),
                "reason": verdict.reason}))

"""데이터 보존(retention) 정책 + 만료 스윕 인터페이스(Mock, ADR-0061).

GDPR 제5조(저장 제한)·개인정보보호법 보존기간 대응. 카테고리별 보존기한(일)을 정의하고,
만료 대상을 정리하는 **스윕 인터페이스**를 제공한다. 현재는 Mock(후보 보고·비변형)이며,
실 삭제는 후속 S5 확장에서 retention 어댑터로 배선한다(외부 인프라 어댑터 허용, DoD).
"""
from __future__ import annotations

from datetime import datetime

# 카테고리 → 보존기한(일). 데모 기본값 — 실 정책은 법무/운영과 협의해 조정.
RETENTION_DAYS: dict[str, int] = {
    "conversation_memory": 365,   # 대화 연속성(컴패니언) — 1년
    "open_loops": 180,            # 미해결 스레드 — 6개월
    "engagement": 365,            # 열람/관심 상태 — 1년
    "orders": 1825,               # 주문 이력 — 5년(거래·세무 보존 의무 고려)
    "audit": 1095,                # 감사 로그 — 3년
}


class RetentionPolicy:
    """보존 정책 조회 + Mock 만료 스윕.

    `audit`(선택)를 주입하면 스윕 시 감사 이벤트를 남긴다(비차단).
    """

    def __init__(self, audit=None) -> None:
        self._audit = audit

    @staticmethod
    def policy() -> dict[str, int]:
        """카테고리별 보존기한(일)(요구사항 5.1)."""
        return dict(RETENTION_DAYS)

    def sweep(self, now: datetime | None = None) -> dict[str, int]:
        """Mock 만료 스윕 — 카테고리별 만료 후보 건수 보고(요구사항 5.2·5.3).

        Mock이므로 실제 데이터를 변형하지 않고 인터페이스만 제공한다(회귀 불변). 실 구현은
        각 저장소를 `now - RETENTION_DAYS[cat]` 기준으로 질의해 만료분을 삭제한다.
        """
        candidates = {cat: 0 for cat in RETENTION_DAYS}
        if self._audit is not None:
            try:
                self._audit.record("retention.sweep", subject="system", detail=candidates)
            except Exception:
                pass
        return candidates

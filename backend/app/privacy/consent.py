"""동의(Consent) scope 확장 — 부여/철회/조회(ADR-0030·ADR-0061).

ADR-0030의 `User.consent.scopes` 모델을 **유지**한다. 본 모듈은 그 위의 헬퍼로,
기능별 scope를 개별 부여/철회하고(요구사항 1) 상태를 조회한다. 새 스키마를 만들지 않는다.

알 수 없는 scope는 거부(ValueError → 라우터가 400 매핑)한다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..domain import Consent, User

# ADR-0030의 기능별 scope 키(동의 차등). 선제 알림 opt-in은 scope가 아님(Preferences).
KNOWN_SCOPES: tuple[str, ...] = ("device_data", "personalization", "engagement", "analytics")


class ConsentStore:
    """User.consent.scopes 위의 scope 부여/철회/조회 헬퍼.

    프로필 출처는 `UserDirectory`(principal_id → User). 변경 후 `upsert`로 반영한다.
    `directory`가 없으면(단위 테스트) User 객체만 직접 변형해 반환한다.
    """

    def __init__(self, directory=None) -> None:
        self._directory = directory

    @staticmethod
    def _validate(scope: str) -> None:
        if scope not in KNOWN_SCOPES:
            raise ValueError(f"unknown consent scope: {scope!r}")

    def _persist(self, user: User) -> None:
        if self._directory is not None:
            self._directory.upsert(user)

    def grant(self, user: User, scope: str) -> Consent:
        """scope 부여(이미 있으면 멱등). 갱신 시각 기록(요구사항 1.1)."""
        self._validate(scope)
        scopes = list(user.consent.scopes)
        if scope not in scopes:
            scopes.append(scope)
        user.consent = Consent(scopes=scopes, updated_at=datetime.now(timezone.utc))
        self._persist(user)
        return user.consent

    def revoke(self, user: User, scope: str) -> Consent:
        """scope 철회 — 해당 scope만 제거, 나머지는 보존(요구사항 1.2)."""
        self._validate(scope)
        scopes = [s for s in user.consent.scopes if s != scope]
        user.consent = Consent(scopes=scopes, updated_at=datetime.now(timezone.utc))
        self._persist(user)
        return user.consent

    @staticmethod
    def status(user: User) -> dict[str, bool]:
        """알려진 scope별 부여 여부(요구사항 1.3)."""
        granted = set(user.consent.scopes)
        return {scope: scope in granted for scope in KNOWN_SCOPES}

"""예산 가드 — 일/세션 비용 상한 + 강등/차단 훅(ADR-0062, 요구사항 3).

인메모리 누적(프로세스 단일). 상한 미설정이면 항상 허용(무제한·회귀 불변). 상한 초과 시:
- 소프트(상한의 `SOFT_RATIO`) 초과 → `should_downgrade`=True(상위→경량 라우팅 다운그레이드 신호).
- 하드(상한 100%) 초과 → `allow`=False(차단 신호). 호출부가 선택적으로 소비(강제하지 않음).
시계는 주입 가능(`now_fn`)해 일 리셋을 결정적으로 테스트한다.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional

# 소프트 임계 = 상한의 이 비율 초과 시 강등 신호.
SOFT_RATIO = 0.8

_DEFAULT_SESSION = "__global__"


def _env_float(name: str) -> Optional[float]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class BudgetGuard:
    """일·세션 누적 비용 추적 + 상한 가드. 상한 None이면 해당 차원 무제한."""

    def __init__(
        self,
        daily_usd: Optional[float] = None,
        session_usd: Optional[float] = None,
        *,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self.daily_usd = daily_usd
        self.session_usd = session_usd
        self._now = now_fn
        self._lock = threading.Lock()
        self._daily_total = 0.0
        self._daily_epoch_day = self._current_day()
        self._session_totals: dict[str, float] = {}

    def _current_day(self) -> int:
        return int(self._now() // 86400)

    def _roll_day_locked(self) -> None:
        day = self._current_day()
        if day != self._daily_epoch_day:  # 날짜 경계 → 일 누적 리셋(요구사항 3.5)
            self._daily_epoch_day = day
            self._daily_total = 0.0

    def add(self, session_id: Optional[str], cost_usd: float) -> None:
        """누적에 비용을 더한다(일·세션)."""
        sid = session_id or _DEFAULT_SESSION
        with self._lock:
            self._roll_day_locked()
            self._daily_total += cost_usd
            self._session_totals[sid] = self._session_totals.get(sid, 0.0) + cost_usd

    def session_total(self, session_id: Optional[str] = None) -> float:
        with self._lock:
            return self._session_totals.get(session_id or _DEFAULT_SESSION, 0.0)

    def daily_total(self) -> float:
        with self._lock:
            self._roll_day_locked()
            return self._daily_total

    def allow(self, session_id: Optional[str] = None) -> bool:
        """하드 상한 미초과면 True. 상한 미설정이면 항상 True(무제한)."""
        sid = session_id or _DEFAULT_SESSION
        with self._lock:
            self._roll_day_locked()
            if self.daily_usd is not None and self._daily_total >= self.daily_usd:
                return False
            sess = self._session_totals.get(sid, 0.0)
            if self.session_usd is not None and sess >= self.session_usd:
                return False
            return True

    def should_downgrade(self, session_id: Optional[str] = None) -> bool:
        """소프트 임계(상한*SOFT_RATIO) 초과면 True(강등 신호). 상한 미설정이면 False."""
        sid = session_id or _DEFAULT_SESSION
        with self._lock:
            self._roll_day_locked()
            if self.daily_usd is not None and self._daily_total >= self.daily_usd * SOFT_RATIO:
                return True
            sess = self._session_totals.get(sid, 0.0)
            if self.session_usd is not None and sess >= self.session_usd * SOFT_RATIO:
                return True
            return False

    def reset(self) -> None:
        with self._lock:
            self._daily_total = 0.0
            self._daily_epoch_day = self._current_day()
            self._session_totals.clear()


_guard: Optional[BudgetGuard] = None
_guard_lock = threading.Lock()


def default_guard() -> BudgetGuard:
    """프로세스 단일 예산 가드 — env 상한으로 구성(미설정=무제한)."""
    global _guard
    if _guard is None:
        with _guard_lock:
            if _guard is None:
                _guard = BudgetGuard(
                    daily_usd=_env_float("COST_DAILY_BUDGET_USD"),
                    session_usd=_env_float("COST_SESSION_BUDGET_USD"),
                )
    return _guard


def reset_default_guard() -> None:
    """테스트용 — 프로세스 단일 가드 재생성(다음 default_guard()가 env 재해석)."""
    global _guard
    with _guard_lock:
        _guard = None

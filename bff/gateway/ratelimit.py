"""BFF 레이트리밋 / 남용 방지 — 에지 토큰버킷 미들웨어(S7, ADR-0063, 요구사항 1).

ADR-0052 계층 분담: 레이트리밋은 **에지(BFF)** 가 소유한다(첫 방어선). 키는 신원(X-User-Id →
X-Guest-Token) 우선, 없으면 클라이언트 IP. 초과 시 `429 {code:"RateLimited", retry_after}` +
`Retry-After` 헤더.

토큰버킷: 버스트 허용·O(1)·stdlib `time.monotonic`만 사용(새 의존성 없음). 인메모리 버킷은 단일
프로세스 가정(MVP) — 멀티 인스턴스 정합은 Redis 어댑터(후속, operations Phase B).

**토글 `RATE_LIMIT` 기본 off → 미들웨어 미등록 = 회귀 불변**(요구사항 6).
"""
from __future__ import annotations

import math
import os
import time
from typing import Optional

# 기본 한도(명시 env 없으면 사용). rate=초당 보충 토큰, capacity=버스트 상한.
_DEFAULT_RATE = 5.0      # 초당 5 요청 보충
_DEFAULT_CAPACITY = 20   # 버스트 최대 20


def _enabled() -> bool:
    return (os.getenv("RATE_LIMIT", "").strip().lower() in ("1", "true", "yes", "on"))


def _float_env(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    try:
        return float(v)
    except ValueError:
        return default


class TokenBucket:
    """단일 키 토큰버킷. monotonic 시계로 보충(요구사항 1.5)."""

    __slots__ = ("rate", "capacity", "_tokens", "_ts", "_clock")

    def __init__(self, rate: float, capacity: float, *, clock=time.monotonic) -> None:
        self.rate = rate
        self.capacity = capacity
        self._tokens = capacity
        self._clock = clock
        self._ts = clock()

    def allow(self) -> tuple[bool, float]:
        """토큰 1개를 소비 시도. (허용여부, retry_after_seconds) 반환."""
        now = self._clock()
        elapsed = now - self._ts
        self._ts = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True, 0.0
        deficit = 1.0 - self._tokens
        retry_after = deficit / self.rate if self.rate > 0 else float("inf")
        return False, retry_after


class RateLimiter:
    """키별 토큰버킷 맵(요구사항 1.2·1.3)."""

    def __init__(self, rate: float = _DEFAULT_RATE, capacity: float = _DEFAULT_CAPACITY,
                 *, clock=time.monotonic) -> None:
        self.rate = rate
        self.capacity = capacity
        self._clock = clock
        self._buckets: dict[str, TokenBucket] = {}

    def check(self, key: str) -> tuple[bool, int]:
        """키의 버킷에서 토큰 1개 소비 시도. (허용, retry_after_초[올림]) 반환."""
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(self.rate, self.capacity, clock=self._clock)
            self._buckets[key] = bucket
        ok, retry_after = bucket.allow()
        return ok, int(math.ceil(retry_after)) if not ok else 0


def client_key(request) -> str:
    """레이트리밋 키 — 신원 우선(X-User-Id → X-Guest-Token), 없으면 IP(요구사항 1.3)."""
    h = request.headers
    uid = h.get("x-user-id")
    if uid:
        return f"user:{uid}"
    gt = h.get("x-guest-token")
    if gt:
        return f"guest:{gt}"
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    return f"ip:{host or 'unknown'}"


def install_ratelimit(app, limiter: Optional[RateLimiter] = None, audit=None) -> Optional[RateLimiter]:
    """토글 on일 때만 레이트리밋 미들웨어를 설치한다(요구사항 1·6).

    - off(기본) → 미들웨어 미등록, None 반환(회귀 불변).
    - on → 초과 시 429 {code:"RateLimited", retry_after} + Retry-After 헤더, 감사 기록(있으면).
    """
    if not _enabled():
        return None

    from fastapi import Request
    from fastapi.responses import JSONResponse

    lim = limiter or RateLimiter(
        rate=_float_env("RATE_LIMIT_RPS", _DEFAULT_RATE),
        capacity=_float_env("RATE_LIMIT_BURST", _DEFAULT_CAPACITY),
    )

    @app.middleware("http")
    async def _ratelimit(request: Request, call_next):
        try:
            key = client_key(request)
            ok, retry_after = lim.check(key)
        except Exception:
            # 미들웨어가 서비스를 깨지 않는다(가용성 우선).
            return await call_next(request)
        if not ok:
            _record_block(audit, key, request.url.path, retry_after)
            return JSONResponse(
                status_code=429,
                content={"code": "RateLimited", "retry_after": retry_after},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)

    return lim


def _record_block(audit, key: str, path: str, retry_after: int) -> None:
    """레이트리밋 차단을 보안 감사에 기록(비차단). audit가 None이면 건너뜀."""
    if audit is None:
        return
    try:
        # backend security 헬퍼가 있으면 사용, 없으면 AuditLog.record로 직접.
        from app.security.audit import RATELIMIT_BLOCK, security_audit
        security_audit(audit, RATELIMIT_BLOCK, subject=key,
                       detail={"path": path, "retry_after": retry_after})
    except Exception:
        try:
            audit.record("security.ratelimit_block", subject=key,
                         detail={"path": path, "retry_after": retry_after})
        except Exception:
            pass

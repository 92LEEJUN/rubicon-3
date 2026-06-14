"""메트릭(인메모리, stdlib only) — 요청 수·에러·지연 히스토그램(S1 관측성).

Prometheus 텍스트 노출(version 0.0.4). 새 의존성 없음 — prometheus_client 미사용.

확장점(기존 대비):
- 요청/에러 카운터 유지(`rubicon_requests_total`·`rubicon_errors_total`).
- **지연 히스토그램** `rubicon_request_duration_seconds`(버킷 `le` + `_sum`·`_count`).
  히스토그램은 Prometheus 규약대로 **누적 버킷**(le=상한 이하 누계)으로 노출한다.
- 가동시간 게이지 유지.

스레드 안전: 카운터 증가는 GIL 하의 단순 가산이지만, 일관 스냅샷을 위해 Lock으로 감싼다.
"""
from __future__ import annotations

import threading
import time

# 기본 지연 버킷(초) — 웹 API 일반 분포. SLO(p95<0.3s 등) 평가에 충분한 해상도.
DEFAULT_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)


class Metrics:
    """프로세스 단위 요청/에러 카운터 + 지연 히스토그램 + 가동시간."""

    def __init__(self, buckets: tuple[float, ...] = DEFAULT_BUCKETS) -> None:
        self.requests = 0
        self.errors = 0
        self._buckets = tuple(sorted(buckets))
        # 각 버킷 상한별 카운트(비누적; 노출 시 누적으로 합산). +Inf는 별도.
        self._bucket_counts = [0 for _ in self._buckets]
        self._inf_count = 0
        self._sum = 0.0
        self._count = 0
        self._lock = threading.Lock()
        self.started = time.monotonic()

    # ── 기록 ────────────────────────────────────────────────────────────────
    def observe(self, duration_seconds: float, *, is_error: bool = False) -> None:
        """요청 1건 기록 — 카운터 증가 + 지연을 히스토그램에 반영."""
        with self._lock:
            self.requests += 1
            if is_error:
                self.errors += 1
            self._sum += duration_seconds
            self._count += 1
            placed = False
            for i, ub in enumerate(self._buckets):
                if duration_seconds <= ub:
                    self._bucket_counts[i] += 1
                    placed = True
                    break
            if not placed:
                self._inf_count += 1

    def incr_error(self) -> None:
        """지연 정보 없이 에러만 집계(예외 전파 경로 등)."""
        with self._lock:
            self.errors += 1

    def uptime(self) -> float:
        return time.monotonic() - self.started

    # ── 노출 ────────────────────────────────────────────────────────────────
    def _cumulative_buckets(self) -> list[tuple[str, int]]:
        """(le 라벨, 누적 카운트) 목록 — Prometheus 히스토그램 규약(누적)."""
        out: list[tuple[str, int]] = []
        running = 0
        for ub, c in zip(self._buckets, self._bucket_counts):
            running += c
            out.append((_fmt_le(ub), running))
        running += self._inf_count
        out.append(("+Inf", running))
        return out

    def prometheus(self, service: str) -> str:
        """Prometheus 텍스트 노출 포맷."""
        with self._lock:
            requests, errors = self.requests, self.errors
            buckets = self._cumulative_buckets()
            hsum, hcount = self._sum, self._count
        up = self.uptime()
        svc = f'service="{service}"'
        lines = [
            "# HELP rubicon_requests_total Total HTTP requests handled.",
            "# TYPE rubicon_requests_total counter",
            f"rubicon_requests_total{{{svc}}} {requests}",
            "# HELP rubicon_errors_total Total HTTP responses with status >= 500 or unhandled errors.",
            "# TYPE rubicon_errors_total counter",
            f"rubicon_errors_total{{{svc}}} {errors}",
            "# HELP rubicon_request_duration_seconds HTTP request latency in seconds.",
            "# TYPE rubicon_request_duration_seconds histogram",
        ]
        for le, c in buckets:
            lines.append(
                f'rubicon_request_duration_seconds_bucket{{{svc},le="{le}"}} {c}')
        lines.append(f"rubicon_request_duration_seconds_sum{{{svc}}} {hsum:.6f}")
        lines.append(f"rubicon_request_duration_seconds_count{{{svc}}} {hcount}")
        lines += [
            "# HELP rubicon_uptime_seconds Process uptime in seconds.",
            "# TYPE rubicon_uptime_seconds gauge",
            f"rubicon_uptime_seconds{{{svc}}} {up:.3f}",
        ]
        return "\n".join(lines) + "\n"


def _fmt_le(ub: float) -> str:
    """버킷 상한을 Prometheus le 라벨 문자열로(정수는 정수처럼, 그 외 소수)."""
    if ub == int(ub):
        return str(int(ub))
    return repr(ub)


# ── 프로세스 공유 인스턴스 ───────────────────────────────────────────────────
# install_observability(엔드포인트/카운팅 미들웨어)와 wiring 미들웨어(상관관계·로깅)가
# **같은** Metrics를 보도록 단일 인스턴스를 공유한다. install이 앱별로 새로 생성하되 마지막
# 것을 여기 보관 → 이중 집계 방지(카운팅은 install 미들웨어만 담당).
_shared: Metrics | None = None


def set_shared(metrics: Metrics) -> None:
    global _shared
    _shared = metrics


def get_shared() -> Metrics | None:
    return _shared

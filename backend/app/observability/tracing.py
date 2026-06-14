"""분산추적 — OTel 스타일 인터페이스 + 콘솔/Mock exporter(S1 관측성, stdlib only).

실 SaaS(OTLP/Jaeger/Datadog 등) 없이 **인터페이스 + 어댑터**만 둔다(production-readiness DoD:
"외부 인프라는 Mock/인터페이스 어댑터 허용"). 토글 `TRACING`(기본 off)일 때만 발동 = 회귀 불변.

구조(OpenTelemetry 모델 차용):
- `Span` — trace_id/span_id/parent_id·이름·시작/종료·속성·상태. context manager.
- `SpanExporter` — `export(span)` 인터페이스. `ConsoleExporter`(rubicon 로거로)·`MockExporter`(인메모리, 테스트).
- `Tracer` — `start_span(name)` 컨텍스트 매니저. 활성 span을 ContextVar로 추적해 부모-자식 연결.
- `NoopTracer` — 토글 off일 때. 아무 것도 내보내지 않음(오버헤드 최소).
- `get_tracer()` — settings/토글에 따라 Noop 또는 실 Tracer 반환.

새 의존성 없음 — opentelemetry 패키지 미사용(인터페이스만 동형).
"""
from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator, Protocol

from .request_context import get_request_id


def tracing_enabled() -> bool:
    """추적 토글 — 기본 off(회귀 불변). 매 호출 평가(런타임 env 반영)."""
    return os.getenv("TRACING", "").strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Span:
    """OTel 스타일 span — trace/span/parent id·타이밍·속성·상태."""

    name: str
    trace_id: str
    span_id: str
    parent_id: str | None = None
    start_ns: int = field(default_factory=time.monotonic_ns)
    end_ns: int | None = None
    attributes: dict[str, object] = field(default_factory=dict)
    status: str = "UNSET"  # UNSET | OK | ERROR

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def set_status(self, status: str) -> None:
        self.status = status

    @property
    def duration_ms(self) -> float | None:
        if self.end_ns is None:
            return None
        return (self.end_ns - self.start_ns) / 1_000_000.0


class SpanExporter(Protocol):
    """완료된 span을 외부로 내보내는 어댑터 경계(실 SaaS는 이 자리에 OTLP 구현)."""

    def export(self, span: Span) -> None: ...


class MockExporter:
    """인메모리 exporter — 테스트·로컬 검증용. 내보낸 span을 리스트에 모은다."""

    def __init__(self) -> None:
        self.spans: list[Span] = []

    def export(self, span: Span) -> None:
        self.spans.append(span)


class ConsoleExporter:
    """완료 span을 `rubicon` 로거로 한 줄 내보낸다(실 SaaS 대체, 로컬 가시성)."""

    def export(self, span: Span) -> None:
        # 지연 import — 로깅 구성 순환/부작용 회피.
        from .logging_setup import log

        log.info(
            "span",
            extra={
                "ctx_event": "span",
                "ctx_span_name": span.name,
                "ctx_trace_id": span.trace_id,
                "ctx_span_id": span.span_id,
                "ctx_parent_id": span.parent_id,
                "ctx_duration_ms": span.duration_ms,
                "ctx_status": span.status,
                **{f"ctx_attr_{k}": v for k, v in span.attributes.items()},
            },
        )


# 현재 활성 span(부모-자식 연결용). 분산 추적의 in-process 컨텍스트 전파.
_active_span: ContextVar[Span | None] = ContextVar("active_span", default=None)


class Tracer:
    """span 생성·exporter로 방출. trace_id는 요청 상관관계(request_id)와 정렬."""

    def __init__(self, exporter: SpanExporter, service: str = "backend") -> None:
        self._exporter = exporter
        self._service = service

    @contextmanager
    def start_span(self, name: str, **attributes: object) -> Iterator[Span]:
        parent = _active_span.get()
        trace_id = parent.trace_id if parent else (get_request_id() or uuid.uuid4().hex)
        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_id=parent.span_id if parent else None,
            attributes={"service": self._service, **attributes},
        )
        token = _active_span.set(span)
        try:
            yield span
            if span.status == "UNSET":
                span.set_status("OK")
        except Exception:
            span.set_status("ERROR")
            raise
        finally:
            span.end_ns = time.monotonic_ns()
            _active_span.reset(token)
            self._exporter.export(span)


class NoopTracer:
    """토글 off일 때의 무동작 tracer — span은 만들되 내보내지 않는다(오버헤드 최소)."""

    @contextmanager
    def start_span(self, name: str, **attributes: object) -> Iterator[Span]:
        span = Span(name=name, trace_id="", span_id="")
        yield span


def get_tracer(service: str = "backend",
               exporter: SpanExporter | None = None) -> Tracer | NoopTracer:
    """토글에 따라 Tracer(콘솔 exporter 기본) 또는 NoopTracer 반환.

    `exporter`를 명시하면 그것을 사용(테스트에서 MockExporter 주입). off면 Noop.
    """
    if not tracing_enabled():
        return NoopTracer()
    return Tracer(exporter or ConsoleExporter(), service=service)

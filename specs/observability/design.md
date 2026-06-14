# 설계 (Design)

> 이 문서는 `requirements.md` 의 요구사항을 **어떻게** 만족시킬지 설명한다.
> 결정 근거·대안은 [ADR-0057](../../docs/adr/0057-observability.md). 기반: ADR-0056
> (`config.get_settings()`·`platform/wiring`·`registry` 시임).

## 개요
기존 `observability.py` 단일 모듈을 **`backend/app/observability/` 패키지**로 분리하고, 책임별
모듈로 나눈 뒤 4가지(상관관계·settings 로깅·지연 히스토그램·추적 인터페이스)를 더한다. **공개
API는 재노출**해 회귀 불변(`from ..observability import install_observability, log`). 모든 신기능은
stdlib only·토글 기본 off.

## 아키텍처

```
요청 ──▶ [wiring 미들웨어: middleware_obs]  (priority=10, 바깥)
            ├─ request_id 바인딩(인바운드 X-Request-Id 이어받기/신규)   (요구사항 1)
            ├─ TRACING on이면 server span 시작(get_tracer)             (요구사항 4)
            └─ 구조화 요청 로그(method·path·status·지연·request_id)     (요구사항 2)
        ──▶ [install 미들웨어: install_observability]  (안쪽)
            └─ 카운팅 + 지연 히스토그램 관측(Metrics.observe)            (요구사항 3)
        ──▶ 라우트 핸들러
응답 ◀── X-Request-Id 에코, /metrics 텍스트(카운터+히스토그램)
```

- 배선: `middleware_obs`가 `wiring.register_middleware(priority=10)`로 자기 미들웨어를 등록한다.
  `registry.py`에 import 한 줄(부수효과 로드, `# noqa: F401`). `internal.py`가 호출하는
  `wiring.apply(app)`가 부착(ADR-0056). install 미들웨어는 `internal.py`가 기존대로
  `install_observability(app)`로 직접 설치(후방 호환). _(요구사항 5-1, 5-3)_
- 두 미들웨어가 같은 `Metrics`를 보도록 `metrics.set_shared/get_shared`로 공유. 카운팅은 install만
  담당해 **이중 집계 방지**. _(요구사항 3)_

## 주요 컴포넌트 / 인터페이스

- **`request_context.py`**: `ContextVar` 기반 request_id. `bind_request_id(id=None) -> (id, token)`·
  `reset_request_id(token)`·`get_request_id()`·`new_request_id()`·헤더 상수 `REQUEST_ID_HEADER`. _(요구사항 1)_
- **`logging_setup.py`**: `configure_logging(settings=None) -> Logger` — settings의 log_level/log_json을
  적용, `JsonLineFormatter`/`PlainFormatter` 선택, 멱등(우리 핸들러 1개), `propagate=False`. 모든
  레코드에 현재 request_id·`ctx_*` 평탄화. 모듈 로드 시 `log` 1회 구성(기존 심볼 호환). _(요구사항 2)_
- **`metrics.py`**: `Metrics(buckets=DEFAULT_BUCKETS)` — `observe(dur, is_error=False)`·`incr_error()`·
  `uptime()`·`prometheus(service) -> str`. 카운터 + 누적 히스토그램(`le`·`_sum`·`_count`·`+Inf`).
  `set_shared/get_shared`로 프로세스 공유. Lock으로 일관 스냅샷. _(요구사항 3)_
- **`tracing.py`**: OTel 스타일 — `Span`(trace_id/span_id/parent_id·attributes·status·duration_ms)·
  `SpanExporter`(Protocol)·`ConsoleExporter`(rubicon 로거)·`MockExporter`(인메모리)·`Tracer.start_span`
  (컨텍스트 매니저, 활성 span ContextVar로 부모-자식)·`NoopTracer`·`get_tracer(service, exporter=None)`·
  `tracing_enabled()`(토글 `TRACING`). _(요구사항 4)_
- **`middleware_obs.py`**: wiring 등록 미들웨어 — request_id 바인딩/에코 + span 래핑 + 구조화 요청 로그.
  install 미들웨어보다 바깥(priority 낮음). _(요구사항 1, 2, 4, 5)_
- **`install.py`**: `install_observability(app, service)` 유지 — /health·/metrics + 카운팅/지연 미들웨어.
  내부적으로 `Metrics`·`logging_setup` 조립. _(요구사항 3, 5-3)_

## 데이터 모델
- **Span**(dataclass): `name·trace_id·span_id·parent_id·start_ns·end_ns·attributes·status(UNSET|OK|ERROR)`.
- **메트릭 시리즈**: `rubicon_requests_total`·`rubicon_errors_total`·`rubicon_uptime_seconds`(기존),
  `rubicon_request_duration_seconds_bucket{le}`·`_sum`·`_count`(신규, 누적). 라벨 `service`.
- **request_id**: uuid4 hex(32자) 또는 인바운드 헤더 값. ContextVar에 보관.

## 에러 처리
- 미들웨어는 응답을 변형하지 않는다(스트리밍/봉투 불변). 예외는 에러로 집계·로그(WARNING) 후 재던짐.
- span 내부 예외는 상태 ERROR로 기록 후 재던짐(요구사항 4-4).
- request_id는 `try/finally`로 항상 reset(컨텍스트 누수 방지).
- 토글 off면 tracer는 Noop(무동작) — 회귀 불변(요구사항 4-1, 5-2).

## 테스트 전략
`backend/tests/test_observability.py`(단위·통합, TestClient):
- 상관관계: 응답 헤더 존재·인바운드 에코·ContextVar bind/reset(요구사항 1).
- 메트릭: 히스토그램 시리즈 노출·누적 단조·+Inf==총수·에러 카운트(요구사항 3).
- 추적: 토글 off=Noop·on=Tracer·MockExporter 수집·부모-자식 trace_id·예외 ERROR(요구사항 4).
- 로깅: log_json→JSON/평문 포맷터·레벨·멱등·request_id/ctx_ 평탄화(요구사항 2).
- 회귀: /health·요청 카운터(기존 test_health 동형) + 전 스위트 green(요구사항 5-2).

## SLO 정의 _(요구사항 5-4)_
> 측정은 위 메트릭으로(아래 PromQL은 실 수집기 연동 시 형태; 현재는 인메모리 노출까지).

| SLI | 목표(SLO) | 측정(메트릭) | 기간/에러버짓 |
|---|---|---|---|
| 가용성 | 성공률 ≥ 99.5% | `1 - rate(rubicon_errors_total) / rate(rubicon_requests_total)` | 30일, 에러버짓 0.5% |
| 지연 p95 | ≤ 300ms | `histogram_quantile(0.95, rate(rubicon_request_duration_seconds_bucket[5m]))` | 30일 |
| 지연 p99 | ≤ 800ms | `histogram_quantile(0.99, ...)` | 30일 |
| 헬스 | `/health` 200 | uptime 게이지 + 외부 프로브 | — |

- 버킷(`DEFAULT_BUCKETS = 5ms..10s`)은 위 p95/p99 임계(0.3s·0.8s) 근방을 포함하도록 정렬해 분위수
  추정 해상도를 확보한다. 에러버짓 소진 시 운영은 신규 위험 배포를 보류(운영 우수성).

## 설계 결정 / 대안
- **패키지 분리 + 공개 API 재노출** — 책임별 모듈로 테스트·교체 용이, 동시에 회귀 불변. (ADR-0057)
- **stdlib only(인터페이스+어댑터)** — prometheus_client/otel-sdk 대신 동형 인터페이스 + 콘솔/Mock
  exporter. 실 SDK는 exporter 교체점. (ADR-0057 기각안 참조)
- **카운팅 단일화** — install 미들웨어만 집계, wiring 미들웨어는 상관관계·로깅·span만(이중 집계 방지).
- **추적 토글 off 기본** — Noop으로 무동작 보장(회귀·오버헤드 없음).

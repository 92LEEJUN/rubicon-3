# 작업 (Tasks)

> `design.md` 를 실제 구현으로 나눈 체크리스트. 끝에 관련 요구사항 번호 표기. 완료는 `[x]`.

## 작업 목록

- [x] 1. `observability.py` → `observability/` 패키지 분리, 공개 API 재노출 _(요구사항 5-3)_
  - [x] 1.1 기존 모듈을 `install.py`로 이동(git mv), `__init__.py`에서 `install_observability`·`log` 재노출
  - [x] 1.2 `from ..observability import install_observability`(internal.py) 그대로 동작 확인

- [x] 2. 요청 상관관계 — `request_context.py` _(요구사항 1)_
  - [x] 2.1 ContextVar 기반 `bind/reset/get/new_request_id` + `REQUEST_ID_HEADER`

- [x] 3. settings 기반 구조화 로깅 — `logging_setup.py` _(요구사항 2)_
  - [x] 3.1 `JsonLineFormatter`/`PlainFormatter` + `configure_logging(settings)`(log_level/log_json)
  - [x] 3.2 멱등(우리 핸들러 1개)·`propagate=False`·request_id/ctx_ 평탄화

- [x] 4. 메트릭 히스토그램 — `metrics.py` _(요구사항 3)_
  - [x] 4.1 `Metrics.observe`(카운터+히스토그램)·누적 버킷·`prometheus()` 확장
  - [x] 4.2 `set_shared/get_shared`(install↔wiring 공유, 이중 집계 방지)
  - [x] 4.3 `install.py`가 새 `Metrics`로 카운팅/지연 미들웨어 + /health·/metrics

- [x] 5. 분산추적 — `tracing.py` _(요구사항 4)_
  - [x] 5.1 `Span`·`SpanExporter`·`ConsoleExporter`·`MockExporter`
  - [x] 5.2 `Tracer.start_span`(부모-자식 trace_id)·`NoopTracer`·`get_tracer`·`tracing_enabled`(토글 `TRACING`)

- [x] 6. 배선 미들웨어 — `middleware_obs.py` + registry append _(요구사항 1, 2, 4, 5-1)_
  - [x] 6.1 wiring 등록 미들웨어(request_id 바인딩/에코 + span + 구조화 요청 로그)
  - [x] 6.2 `registry.py`에 import 한 줄 append(`# noqa: F401`)

- [x] 7. 테스트 — `tests/test_observability.py` _(요구사항 1~5)_
  - [x] 7.1 상관관계·메트릭·추적·로깅·회귀 케이스
  - [x] 7.2 전 스위트 green·`ruff check backend/` 클린 확인 _(요구사항 5-2)_

- [x] 8. 문서 — ADR-0057 + 본 스펙 3종 + SLO 정의 _(요구사항 5-4)_

## 진행 메모
- 카운팅은 `install` 미들웨어가 단독 담당(wiring 미들웨어는 상관관계·로깅·span만) → 이중 집계 방지.
- 추적 토글은 `TRACING`(기본 off, Noop). 로깅/메트릭은 ADR-0056의 `LOG_LEVEL`·`LOG_JSON`·`APP_ENV`·
  `METRICS_ENABLED`를 그대로 따른다(신규 토글 최소화).
- main 통합 주의: `registry.py`의 append 한 줄(`from ..observability import middleware_obs ...`),
  토글 env `TRACING`. 계약 변경 없음(응답에 `X-Request-Id` 헤더·`/metrics` 히스토그램 시리즈 부가).

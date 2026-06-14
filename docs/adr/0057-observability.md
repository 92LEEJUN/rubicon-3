# ADR-0057: 관측성(Observability) — 상관관계·메트릭 히스토그램·추적 인터페이스·SLO

- **상태**: 채택
- **관련**: [`specs/observability/`](../../specs/observability/requirements.md), [`docs/production-readiness.md`](../production-readiness.md)(S1 스트림·12-Factor #14 Telemetry·WA 운영 우수성), [operations.md](../operations.md), ADR-0056(환경 구성 토대·배선 시임), 12-Factor(XIV Telemetry), OpenTelemetry(트레이스 모델)
- **비고**: ADR-0056의 `config.get_settings()`·`platform/wiring`·`registry` 토대 **위에** 얹는다(Phase 0 의존). 기존 `observability.py`(gap 8: /health·/metrics·JSON 로깅)를 확장한다.

## 배경
MVP의 관측성은 `/health`·`/metrics`(요청/에러 카운터)와 JSON 한 줄 로깅까지다
(`production-readiness.md` 15-Factor #14 = 🟡, "추적·SLO 없음"). 프로덕션 운영(Well-Architected
운영 우수성)에는 다음이 빠져 있다:
1. **요청 상관관계** — 한 요청을 가로지르는 로그·이벤트를 잇는 `request_id`가 없어 디버깅이 어렵다.
2. **로깅이 환경을 따르지 않음** — 로거가 INFO·JSON 고정이라 ADR-0056의 `log_level`/`log_json`
   (dev=DEBUG·평문, prd=INFO·JSON)를 반영하지 못한다.
3. **메트릭 해상도 부족** — 카운터만 있고 **지연 분포(히스토그램/버킷)** 가 없어 p95/p99·SLO를
   평가할 수 없다.
4. **분산추적 부재** — 트레이스 모델·exporter 경계가 없다. 단, 실 SaaS(OTLP/Jaeger 등)는 범위 외다.
5. **SLO 미정의** — 목표·에러버짓·측정 방법이 문서화돼 있지 않다.

제약: **새 pip 의존성 금지(stdlib only)**, **토글 기본 off=회귀 불변(스트랭글러)**, 앱 팩토리
(`api/internal.py`)는 직접 편집하지 않고 ADR-0056 배선 시임으로만 배선(병렬 충돌 회피).

## 결정
관측성을 `observability.py` 단일 모듈에서 **`observability/` 패키지**로 분리하고, 4가지를 더한다.
**공개 API(`install_observability`·`log`)는 그대로 재노출**해 회귀 불변(internal.py가 직접 호출).

- **① 요청 상관관계(request_id)** — `request_context.py`가 `ContextVar`로 요청별 ID를 보관한다.
  미들웨어가 인바운드 `X-Request-Id`를 이어받거나 새로 생성해 바인딩하고 응답 헤더로 에코한다.
  로깅·트레이스가 같은 ID를 읽어 상관관계를 가진다(in-process 컨텍스트 전파).
- **② settings 기반 구조화 로깅** — `logging_setup.py`가 `config.get_settings()`의
  `log_level`/`log_json`을 따른다. `log_json` on→JSON 한 줄, off→평문. 레벨도 settings를 따른다.
  기존 `rubicon` 로거·`ctx_` 평탄화·`propagate=False`는 유지. 모든 레코드에 현재 `request_id`를 부착.
- **③ 메트릭 히스토그램** — `metrics.py`가 기존 카운터(`rubicon_requests_total`·`_errors_total`·
  `_uptime_seconds`)에 **지연 히스토그램** `rubicon_request_duration_seconds`(누적 버킷 `le` +
  `_sum`·`_count`)를 더한다. Prometheus 규약(누적 버킷, +Inf == 총 관측 수)을 따른다. 인메모리·Lock.
- **④ 분산추적 인터페이스 + 콘솔/Mock exporter(토글)** — `tracing.py`가 OTel 스타일 모델(`Span`·
  `Tracer`·`SpanExporter`)을 둔다. 실 SaaS 자리에는 **`ConsoleExporter`(rubicon 로거)·`MockExporter`
  (인메모리·테스트)** 어댑터만(외부 인프라는 Mock/인터페이스 허용 — DoD). 토글 `TRACING` on일 때만
  실 tracer, off면 `NoopTracer`(span은 주되 내보내지 않음 = 오버헤드·동작 없음). trace_id는
  request_id와 정렬하고 활성 span ContextVar로 부모-자식을 잇는다.
- **배선은 시임으로만** — `middleware_obs.py`가 `wiring.register_middleware(priority=10)`로 상관관계·
  로깅·span 미들웨어를 등록한다(install 미들웨어보다 바깥 = request_id 먼저 바인딩). `registry.py`에
  **import 한 줄 append**(부수효과 로드, `# noqa: F401`)로 로드. `internal.py`는 비편집.
- **이중 집계 방지** — 카운팅·지연 측정은 `install_observability` 미들웨어가 단독 담당하고, wiring
  미들웨어는 상관관계·로깅·span만. 두 미들웨어는 `metrics.set_shared`/`get_shared`로 같은 인스턴스 공유.
- **SLO 정의 문서** — `specs/observability/design.md`에 가용성·지연(p95/p99) 목표·에러버짓·측정 쿼리를
  명시(메트릭으로 측정 가능하게 버킷을 정렬).

> 본 ADR은 **구조 결정**이다. 토글 기본 off라 미들웨어/추적은 동작을 바꾸지 않고(응답 불변), 상관관계·
> 로깅 표현만 settings를 따른다(dev 평문/prd JSON). 실 트레이싱 백엔드 연동은 후속(범위 외).

## 대안 / 기각
- **새 의존성(prometheus_client·opentelemetry-sdk) 채택** — 표준 구현을 즉시 얻지만 **stdlib only 제약
  위반**·빌드/공급망 표면 증가. **기각** — 인터페이스 동형 + 어댑터 경계로 충분(실 SDK는 어댑터 교체점).
- **`observability.py` 단일 모듈 유지(인라인 확장)** — 파일 하나가 로깅·메트릭·추적·미들웨어를 모두
  떠안아 비대·결합. **기각** — 책임별 모듈 분리(테스트·교체 용이), 단 공개 API는 재노출로 호환.
- **앱 팩토리(internal.py)에 미들웨어 직접 추가** — 병렬 스트림과 공유 라인 충돌. **기각** —
  ADR-0056 배선 시임(register_middleware + registry append)으로만 배선.
- **추적을 항상 on** — 회귀·오버헤드. **기각** — 토글 뒤(기본 off), Noop으로 무동작 보장.

## 영향
- **operations.md** — 관측성 운영 면(상관관계 ID·지연 SLO·로그 레벨/포맷의 환경 동형) 추가 대상.
  본 ADR이 그 근거. `production-readiness.md`(S1)는 main이 통합 시 #14·운영 우수성 셀을 갱신.
- **계약** — 외부 노출 봉투/엔드포인트 계약 **추가 없음**. `/metrics` 텍스트에 히스토그램 시리즈가
  늘고, 응답에 `X-Request-Id` 헤더가 더해질 뿐(표현 부가, 기존 필드 불변) → 3계층 동기화 불필요.
- **후속 스트림** — S6(비용·캐싱)·S9(딜리버리/DORA)는 이 메트릭/추적 위에 LLM 비용 메트릭·배포
  관측을 얹는다. 추적 exporter는 실 OTLP 어댑터로 교체(범위 외).
- **토글 env** — `TRACING`(추적, 기본 off). 로깅/메트릭은 ADR-0056 `LOG_LEVEL`·`LOG_JSON`·
  `APP_ENV`·`METRICS_ENABLED`를 그대로 따른다(신규 토글 추가 최소화).

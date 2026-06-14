# 요구사항 (Requirements)

## 개요
프로덕션 준비도 프로그램 **S1 관측성** 스트림. MVP의 `/health`·`/metrics`(카운터)·JSON 로깅을
프로덕션 수준으로 끌어올린다: 요청 상관관계(request_id), 환경(설정)을 따르는 구조화 로깅, 지연
히스토그램이 포함된 메트릭, 토글 뒤의 분산추적 인터페이스(+콘솔/Mock exporter), SLO 정의. 모두
**stdlib only**, **토글 기본 off=회귀 불변**(스트랭글러), ADR-0056의 config·배선 시임 위에 얹는다.

## 요구사항 목록

### 요구사항 1: 요청 상관관계(request_id)

**User Story:**
운영자로서, 한 요청을 가로지르는 로그·이벤트를 하나의 ID로 잇기를 원한다, 그래서 분산된 로그에서
특정 요청의 흐름을 추적·디버깅할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 요청이 들어오면 THEN 시스템은 고유 `request_id`를 생성해 요청 컨텍스트에 바인딩해야 한다 (SHALL).
2. IF 인바운드 요청에 `X-Request-Id` 헤더가 있으면 THEN 시스템은 그 값을 이어받아 상관관계 ID로
   사용해야 한다 (SHALL).
3. WHEN 응답을 반환할 때 THEN 시스템은 해당 `request_id`를 응답 헤더로 에코해야 한다 (SHALL).
4. WHILE 요청을 처리하는 동안 시스템은 그 요청의 로그·트레이스에 동일 `request_id`를 부착해야 한다 (SHALL).

### 요구사항 2: 환경(설정)을 따르는 구조화 로깅

**User Story:**
운영자로서, 로그의 레벨·포맷이 환경별 설정을 따르기를 원한다, 그래서 dev는 사람이 읽는 평문으로,
운영(prd)은 집계 가능한 JSON으로 일관되게 볼 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 로깅을 구성할 때 THEN 시스템은 `config.get_settings()`의 `log_level`을 적용해야 한다 (SHALL).
2. IF `log_json`이 true이면 THEN 시스템은 JSON 한 줄 포맷으로, false이면 평문 포맷으로 출력해야 한다 (SHALL).
3. WHEN 로깅을 재구성할 때 THEN 시스템은 우리 핸들러를 중복 부착하지 않아야 한다(멱등) (SHALL).
4. WHILE 기존 `rubicon` 로거·`ctx_` 평탄화 규칙을 유지하는 동안 시스템은 `propagate=False`를
   유지해야 한다(uvicorn/print 로그 혼입 방지) (SHALL).

### 요구사항 3: 메트릭 확장(지연 히스토그램·버킷)

**User Story:**
운영자로서, 요청 지연의 분포(히스토그램)를 원한다, 그래서 p95/p99와 SLO 충족 여부를 측정할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN `/metrics`를 조회할 때 THEN 시스템은 기존 카운터(요청·에러·가동시간)와 함께 지연 히스토그램
   `rubicon_request_duration_seconds`(버킷 `le`·`_sum`·`_count`)를 노출해야 한다 (SHALL).
2. WHEN 히스토그램을 노출할 때 THEN 버킷은 Prometheus 규약대로 **누적**(le 이하 누계)이고 `+Inf`
   버킷은 총 관측 수와 같아야 한다 (SHALL).
3. WHEN 요청이 처리되면 THEN 시스템은 그 지연을 히스토그램에 1건 반영해야 한다 (SHALL).
4. IF 응답이 5xx이거나 예외가 전파되면 THEN 시스템은 에러 카운터를 증가시켜야 한다 (SHALL).

### 요구사항 4: 분산추적 인터페이스 + 콘솔/Mock exporter(토글)

**User Story:**
운영자로서, 실 SaaS 없이도 추적 구조(span·exporter)를 갖추기를 원한다, 그래서 나중에 실 백엔드를
어댑터 교체만으로 붙일 수 있고 지금은 토글 뒤에서 안전하게 검증할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 추적 토글(`TRACING`)이 off(기본)이면 THEN 시스템은 무동작 tracer를 사용해 동작을 바꾸지
   않아야 한다(회귀 불변) (SHALL).
2. IF `TRACING`이 on이면 THEN 시스템은 span을 생성해 exporter(기본 콘솔)로 내보내야 한다 (SHALL).
3. WHEN 자식 span을 시작할 때 THEN 시스템은 부모와 동일한 trace_id를 잇고 parent_id를 연결해야 한다 (SHALL).
4. WHEN span 안에서 예외가 발생하면 THEN 시스템은 그 span 상태를 ERROR로 기록해야 한다 (SHALL).
5. WHILE 테스트하는 동안 시스템은 인메모리 `MockExporter`로 내보낸 span을 검증 가능하게 해야 한다 (SHALL).

### 요구사항 5: 배선·회귀 불변·SLO 문서

**User Story:**
개발자로서, 관측성이 앱 팩토리를 직접 편집하지 않고 배선되며 기존 동작을 회귀시키지 않기를 원한다,
그래서 병렬 스트림과 충돌 없이 안전하게 통합할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 관측성 미들웨어를 배선할 때 THEN 시스템은 `wiring.register_middleware`로 등록하고
   `registry.py`에 import 한 줄만 추가해야 한다(`internal.py` 비편집) (SHALL).
2. WHEN 기존 테스트 스위트를 실행하면 THEN 시스템은 전부 green이어야 한다(회귀 불변) (SHALL).
3. WHEN 기존 공개 API(`install_observability`·`log`)를 import하면 THEN 시스템은 동일 시그니처로
   동작해야 한다(후방 호환) (SHALL).
4. WHEN 설계 문서를 작성할 때 THEN 시스템(문서)은 가용성·지연 SLO와 측정 방법을 정의해야 한다 (SHALL).

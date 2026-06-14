# 요구사항 (Requirements) — S4 API 성숙(API-first)

## 개요
프로덕션 준비도(`docs/production-readiness.md`)의 **12-Factor #2 (API first)** 갭을 메운다.
현재 계약은 문서(`docs/api-contract.md`)와 `frontend/src/types/contract.ts`로만 존재하고,
**버저닝/deprecation 정책·기계가 읽는 스키마(OpenAPI)·스키마→타입 생성·계약 테스트**가 없다.
이 작업은 그 넷을 **추가형(하위호환)**으로 세운다. 기존 엔드포인트/계약 형태와 동작은 불변이다.

## 요구사항 목록

### 요구사항 1: API 버저닝/deprecation 정책
**User Story:** API 소비자(FE/BFF/외부)로서, 계약이 바뀔 때 어떤 규칙으로 버전이 매겨지고
언제·어떻게 폐기되는지 알기를 원한다, 그래서 통합을 안전하게 유지할 수 있다.

**수용기준:**
1. WHEN 계약 변경이 발생할 때 THEN 시스템 문서는 **버전 식별 규칙**(경로/헤더)과
   **하위호환 vs 파괴적 변경**의 구분, **deprecation 절차**(고지·sunset 헤더·유예기간)를
   명시해야 한다 (SHALL).
2. WHEN 클라이언트가 버전 헤더(`X-API-Version`) 없이 호출할 때 THEN 시스템은 **기존 동작과
   동일**(기본 버전)해야 한다 (SHALL, 회귀 불변).
3. IF 응답에 버전 메타가 필요하면 THEN 추가형 응답 헤더(`X-API-Version`)로만 노출하고
   **본문 스키마는 바꾸지 않아야** 한다 (SHALL).
4. WHEN deprecation을 고지할 때 THEN `Deprecation`·`Sunset` 표준 헤더 규칙을 따라야 한다 (SHALL).

### 요구사항 2: OpenAPI 스펙 export
**User Story:** 통합 담당자로서, BE의 노출 인터페이스를 **기계가 읽는 단일 산출물**로 떨구기를
원한다, 그래서 타입 생성·계약 점검·문서화의 입력으로 쓸 수 있다.

**수용기준:**
1. WHEN export 스크립트를 실행할 때 THEN 시스템은 FastAPI 기본 schema를 **OpenAPI JSON 파일**로
   생성해야 한다 (SHALL).
2. WHEN export할 때 THEN **새 무거운 pip 의존성 없이** stdlib + 기존 FastAPI만 사용해야 한다 (SHALL).
3. WHEN export할 때 THEN 산출물에 **버전 메타**(api-contract 버전)를 포함해야 한다 (SHALL).

### 요구사항 3: 스키마 → TS 타입 생성(드리프트 점검)
**User Story:** FE 개발자로서, BE 스키마에서 TS 타입을 **생성**해 `contract.ts`와 드리프트를
점검하기를 원한다, 그래서 손으로 쓴 계약이 BE와 어긋나는지 조기에 잡을 수 있다.

**수용기준:**
1. WHEN 생성 스크립트를 실행할 때 THEN OpenAPI(또는 pydantic) 스키마에서 **TS 타입 파일**을
   **별도 산출물**로 생성해야 한다 (SHALL — `contract.ts`를 덮어쓰지 않는다).
2. WHEN 생성할 때 THEN **새 무거운 pip 의존성 없이** 동작해야 한다 (SHALL).
3. IF 생성 타입과 `contract.ts` 사이에 드리프트가 있으면 THEN 점검은 **드리프트를 보고**해야
   한다 (SHALL, 비차단 — 손-작성 계약이 정본이므로 경고 수준).

### 요구사항 4: 계약 테스트 하니스(경량)
**User Story:** 통합 담당자로서, BE 응답 shape이 `contract.ts`의 키와 정합하는지 **자동 점검**
하기를 원한다, 그래서 계약 드리프트를 CI에서 잡을 수 있다.

**수용기준:**
1. WHEN 계약 테스트를 실행할 때 THEN BE 실제 응답(대표 엔드포인트)의 **키 집합**이
   `contract.ts`가 기대하는 키와 정합함을 검증해야 한다 (SHALL).
2. WHEN 테스트를 실행할 때 THEN **LLM/네트워크 없이**(Mock·TestClient) 결정적으로 돌아야 한다 (SHALL).
3. WHEN 테스트가 추가될 때 THEN 기존 스위트(`backend/tests`)를 깨지 않아야 한다 (SHALL, green 유지).

## 비범위
- 실제 다중 버전(v1/v2) 병행 라우팅·라우터 분기는 후속(정책만 세움, 경량 헤더 미들웨어까지).
- 외부 공개 API 게이트웨이·SDK 배포·Pact broker. 경량 in-repo 계약 점검까지만.
- `contract.ts` 자동 갱신(역방향). 본 작업은 점검(drift report)까지.

# 설계 (Design) — S4 API 성숙(API-first)

## 개요
요구사항 1~4를 **추가형·하위호환**으로 만족시킨다. 기존 엔드포인트/계약(`docs/api-contract.md`
§2·§2.4, `frontend/src/types/contract.ts`)과 BE 라우트(`backend/app/api/internal.py`)는
**한 줄도 바꾸지 않는다**. 새 코드는 별도 모듈/스크립트/테스트로 얹고, 버전 헤더는 Phase 0
배선 시임(`platform/registry.register_middleware`)으로 등록만 한다.

기반 문서 참조:
- 계약 표면: `docs/api-contract.md` §2(클라이언트)·§2.4(내부) — 본 작업은 여기에 **버저닝 섹션 §7**을 append.
- 공유 타입: `frontend/src/types/contract.ts` — 드리프트 점검의 정본.
- 배선: `docs/adr/0056-environment-config-baseline.md`(registry/wiring 시임).

## 아키텍처

```
                    ┌────────────────────────────────────────────────┐
                    │ backend/app/openapi.py  (export 헬퍼)           │
   internal.app ───▶│  build_openapi(app) → dict (+ x-api-version)    │
                    └───────────────┬────────────────────────────────┘
                                    │
        scripts/export_openapi.py ──┤──▶ build/openapi.json   (요구사항 2)
                                    │
        scripts/gen_types.py ───────┴──▶ frontend/src/types/contract.generated.ts (요구사항 3)
                                         + drift report vs contract.ts

   backend/app/platform/ApiVersionMiddleware (register_middleware)
        → 응답에 X-API-Version 헤더 부착(요구사항 1-2·1-3, 본문 불변)

   backend/tests/test_contract.py  → TestClient로 응답 키 ↔ contract.ts 정합(요구사항 4)
```

## 주요 컴포넌트 / 인터페이스

### 1. `backend/app/openapi.py` (신규, export 헬퍼) — 요구사항 2
- `API_VERSION: str` — 계약 버전 단일 상수(예: `"2025-06-01"` 날짜 기반). api-contract §7과 동기.
- `build_openapi(app) -> dict` — `app.openapi()`(FastAPI 기본)를 호출해 schema dict를 얻고,
  최상위에 `info.x-api-version = API_VERSION`을 주입(추가형, 기존 schema 불변).
- `register_version_middleware()` — `registry.register_middleware`로 응답 헤더 미들웨어를 등록.
  **이 모듈을 import하는 것만으로 등록 부수효과**가 일어나도록(wiring 한 줄 append와 동일 패턴).
- 미들웨어는 HTTP 응답에 `X-API-Version: <API_VERSION>` 헤더만 추가(요구사항 1-2·1-3).
  WS/스트림 응답 본문은 만지지 않는다(회귀 불변).

### 2. `scripts/export_openapi.py` (신규) — 요구사항 2
- `python scripts/export_openapi.py [--out build/openapi.json]`.
- `backend/app/api/internal.py:app` import → `openapi.build_openapi(app)` → JSON 파일로 dump.
- stdlib(`json`·`argparse`·`pathlib`)만. 종료 코드 0/비0으로 성공·실패.

### 3. `scripts/gen_types.py` (신규) — 요구사항 3
- `python scripts/gen_types.py [--openapi build/openapi.json] [--out frontend/src/types/contract.generated.ts] [--check]`.
- OpenAPI `components.schemas`(pydantic 모델 → JSON Schema)를 **경량 매퍼**로 TS interface로 변환:
  - `string→string`, `integer|number→number`, `boolean→boolean`, `array→T[]`,
    `object(additionalProperties)→Record<string, ...>`, `$ref→타입명`, `anyOf(...null)→ ... | null`.
  - 매핑 못 하는 건 `unknown`으로 폴백(비차단).
- 산출물은 **`contract.generated.ts`(별도 파일)** — `contract.ts`를 덮지 않는다(요구사항 3-1).
- `--check`: 생성 타입의 **모델/필드 키**를 `contract.ts`의 키(정규식 추출)와 비교해
  **드리프트만 보고**(경고·종료 0; 정본은 손-작성 `contract.ts`이므로 비차단, 요구사항 3-3).
- openapi.json이 없으면 export를 먼저 호출(또는 안내). 새 의존성 없음.

### 4. `backend/tests/test_contract.py` (신규) — 요구사항 4
- `TestClient(app)`로 대표 엔드포인트 응답을 받아 **키 집합**을 검증:
  - `/internal/devices` → 각 항목이 `Device` 키 포함.
  - `/internal/home` → `Template`(kind=`home_summary`, `data`) shape.
  - `/internal/resume` → `ResumePayload`(`has_context` 등) 키 ⊆ contract.ts.
  - 미확인 `/internal/orders` POST → `409 ConfirmationRequired` + `template`(`confirmation`).
- `contract.ts`에서 **CtaKind·TemplateKind·Chunk 봉투 키**를 정규식으로 추출해, BE가 쓰는
  template kind(`home_summary`·`confirmation`·`bridge`)·chunk type(`delta`·`section`·`done`·`error`)이
  contract.ts에 **존재**함을 단언(양방향 정합 점검).
- `X-API-Version` 헤더가 응답에 실리는지(요구사항 1) 단언.
- LLM off·Mock 컨테이너(기존 conftest)로 결정적.

## 데이터 모델
신규 도메인 데이터 모델 없음. `API_VERSION` 상수만 추가. OpenAPI/생성 TS는 **기존**
pydantic 모델·라우트에서 파생되는 산출물이다(정의가 아니라 투영).

## 버저닝 정책 (api-contract §7 append) — 요구사항 1
- **버전 식별** — 날짜 기반 계약 버전(`API_VERSION`). 응답 헤더 `X-API-Version`로 노출(추가형).
  경로 버저닝(`/v1`)은 **파괴적 변경이 불가피할 때만** 도입(현재 미사용, 정책만 명시).
- **하위호환(버전 안 올림)** — 필드 추가, 새 엔드포인트, 새 optional 파라미터, 새 enum 값
  (permissive `kind`). FE는 미지 값을 폴백 처리(contract.ts 주석 규약).
- **파괴적(새 버전 필요)** — 필드 제거/이름변경/타입변경, 필수 파라미터 추가, 상태코드 의미 변경.
- **deprecation 절차** — `Deprecation: true`(또는 날짜)·`Sunset: <RFC1123>` 헤더로 고지,
  유예기간 동안 양 버전 병행, 3계층(`api-contract`·`contract.ts`·`bff/gateway`) 동기.

## 에러 처리
- export/gen 스크립트는 실패 시 명확한 메시지 + 비0 종료. 부분 매핑 실패는 `unknown` 폴백(비차단).
- 미들웨어는 예외를 던지지 않음(헤더 부착만). 등록 항목 없으면 무동작(회귀).

## 테스트 전략
- `backend/tests/test_contract.py` — 기존 pytest 스위트에 합류(LLM off·Mock).
- 스크립트는 CI 게이트가 아니라 **개발/점검 도구**(수동 실행). DoD에서 실제 실행해 산출물 확인.
- 회귀: 기존 `test_internal_api.py`·`test_health.py` 등 전부 green 유지(헤더는 추가형).

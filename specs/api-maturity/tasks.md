# 작업 (Tasks) — S4 API 성숙(API-first)

> 각 항목 끝의 (요구사항 N)은 `requirements.md` 번호. 추가형·하위호환만 — 기존 라우트/계약 불변.

## 1. 문서 — 버저닝/deprecation 정책
- [x] `docs/api-contract.md`에 **§7 버저닝 / Deprecation 정책** 섹션 append (요구사항 1)
  - [x] 버전 식별 규칙(`X-API-Version` 헤더·날짜 버전·경로 버저닝은 파괴 변경시) (요구사항 1-1)
  - [x] 하위호환 vs 파괴적 변경 구분표 (요구사항 1-1)
  - [x] deprecation 절차(`Deprecation`·`Sunset` 헤더·유예·3계층 동기) (요구사항 1-4)

## 2. OpenAPI export 헬퍼 + 스크립트
- [x] `backend/app/openapi.py` 신규 — `API_VERSION`·`build_openapi(app)`(x-api-version 주입) (요구사항 2-1·2-3)
- [x] 응답 `X-API-Version` 헤더 미들웨어를 `registry.register_middleware`로 등록(import 부수효과) (요구사항 1-2·1-3)
- [x] `backend/app/platform/wiring.py`에 openapi 모듈 import 한 줄 append(등록 활성) (요구사항 1-2)
- [x] `scripts/export_openapi.py` 신규 — app import → build_openapi → JSON dump(stdlib) (요구사항 2-1·2-2)

## 3. 스키마 → TS 타입 생성
- [x] `scripts/gen_types.py` 신규 — OpenAPI schemas → TS interface(경량 매퍼, 새 의존성 없음) (요구사항 3-1·3-2)
- [x] 산출물은 `contract.generated.ts`(별도 파일, contract.ts 불변) (요구사항 3-1)
- [x] `--check` 모드 — generated ↔ contract.ts 드리프트 보고(비차단) (요구사항 3-3)

## 4. 계약 테스트 하니스
- [x] `backend/tests/test_contract.py` 신규 — TestClient로 응답 키 ↔ contract.ts 정합 (요구사항 4-1)
- [x] template kind·chunk type 양방향 존재 점검 (요구사항 4-1)
- [x] `X-API-Version` 헤더 단언 (요구사항 1)
- [x] LLM off·Mock 결정적, 기존 스위트 green 유지 (요구사항 4-2·4-3)

## 5. ADR + 검증
- [x] `docs/adr/0060-api-maturity.md` 작성(결정·대안·기각) (요구사항 1~4)
- [x] `ruff check backend/` 클린 / `cd backend && python -m pytest` green
- [x] `scripts/export_openapi.py`·`scripts/gen_types.py` 실제 실행 → 산출물 생성 확인 (요구사항 2·3)

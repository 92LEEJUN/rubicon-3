# ADR-0060: API 성숙(API-first) — 버저닝/Deprecation 정책 · OpenAPI export · 스키마→타입 · 계약 테스트

- **상태**: 채택
- **관련**: [`specs/api-maturity/`](../../specs/api-maturity/requirements.md), [`docs/api-contract.md`](../api-contract.md) §7, [`docs/production-readiness.md`](../production-readiness.md)(S4·12-Factor #2), ADR-0056(환경·배선 시임), `frontend/src/types/contract.ts`
- **스트림**: S4(API 성숙) — 프로덕션 준비도 12-Factor #2 갭(버저닝·OpenAPI·계약 테스트 부재).

## 배경
계약(`docs/api-contract.md` §6)에 "Rate limit·버저닝 정책은 후속"이라 적혀 있고, 계약은
**문서와 손-작성 `contract.ts`로만** 존재한다. 기계가 읽는 스키마(OpenAPI)·스키마에서 파생한
타입·계약 드리프트 자동 점검이 없어 BE↔(BFF·FE) 통합이 조용히 어긋날 수 있다(12-Factor #2 미충족).
이를 **추가형·하위호환**으로 메운다. 기존 엔드포인트/계약 형태·동작은 불변이어야 한다.

## 결정
1. **버저닝/Deprecation 정책 문서화** — `docs/api-contract.md`에 **§7**을 append. 날짜 기반 계약
   버전 + 응답 헤더 `X-API-Version`(추가형), 하위호환 vs 파괴적 변경 구분, deprecation 절차
   (`Deprecation`·`Sunset` 헤더·유예·3계층 동기). 경로 버저닝(`/v1`)은 **파괴 변경이 불가피할
   때만** 도입(현재 미사용, 정책만 명시).
2. **경량 버전 헤더 미들웨어** — `backend/app/openapi.py`가 `registry.register_middleware`로
   응답에 `X-API-Version` 헤더만 부착(본문·상태코드·스트림 불변). `platform/wiring.py`에 import
   한 줄 append로 활성(ADR-0056 배선 시임 — 앱 팩토리/`internal.py` 기존 라인 미편집).
3. **OpenAPI export** — `backend/app/openapi.py:build_openapi(app)`가 FastAPI 기본 `app.openapi()`에
   `info.x-api-version`만 주입(추가형). `scripts/export_openapi.py`가 `build/openapi.json`으로 dump.
   stdlib + 기존 FastAPI만(새 무거운 의존성 없음).
4. **스키마 → TS 타입 생성** — `scripts/gen_types.py`가 OpenAPI `components.schemas`를 경량 매퍼로
   TS interface로 변환, **별도 산출물 `frontend/src/types/contract.generated.ts`**로 떨군다
   (`contract.ts` 정본 불변). `--check`는 generated ↔ contract.ts 드리프트를 **보고만** 한다(비차단).
5. **계약 테스트 하니스** — `backend/tests/test_contract.py`가 `TestClient`로 대표 응답 키 ↔
   `contract.ts` 키(template kind·chunk type) 정합과 `X-API-Version` 헤더를 단언(LLM off·Mock·결정적).

## 대안 / 기각
- **즉시 경로 버저닝(`/v1` 전면 도입)** — 모든 라우트를 옮겨야 해 기존 계약 형태가 바뀌고
  BFF·FE 동시 변경 강제. **기각** — 현재 파괴 변경이 없으므로 정책만 세우고 헤더 버전으로 충분.
- **`datamodel-code-generator`·`openapi-typescript` 등 외부 제너레이터 도입** — 무거운 새 pip/npm
  의존성. **기각**(과제 제약) — 경량 자체 매퍼로 드리프트 점검 목적엔 충분(완벽한 타입은 비목표).
- **`contract.ts`를 생성물로 대체(역방향 자동 갱신)** — 손-작성 계약이 정본(permissive kind 주석
  규약 등 BE 스키마에 없는 의미 포함). **기각** — 생성물은 **별도 파일 + drift 점검**으로 보조만.
- **Pact broker·소비자주도 계약(CDC) 풀스택** — 인프라 과대. **기각** — in-repo 경량 키 정합으로 시작.

## 영향
- **`docs/api-contract.md`** — §6의 "버저닝 후속"이 §7 정책으로 구체화(추가, 기존 §1~§5 불변).
- **`bff/gateway`·`frontend`** — 계약 형태 불변이라 변경 불필요. 향후 파괴 변경 시 §7 절차로 3계층 동기.
- **회귀** — 버전 헤더는 추가형(본문 불변), 미들웨어 무등록 시 무동작. 기존 스위트 green 유지.
- **production-readiness** — S4 항목의 근거. (이 ADR은 매트릭스 셀 상태를 직접 바꾸지 않음 —
  추적 문서는 main이 머지 시 갱신.)

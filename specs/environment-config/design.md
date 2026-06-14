# 설계 (Design) — 환경 계층 & 구성 토대

> 요구사항 1~4 충족. 근거: [ADR-0056](../../docs/adr/0056-environment-config-baseline.md).

## 개요
중앙 `Settings`(BE) + 동형 구성(BFF/FE) + append-only **배선 시임**. 모두 추가형(기존 `os.getenv`·
`apiBase` 불변). 환경 기본값은 명시 env에 의해 덮인다.

## 주요 컴포넌트
- **`backend/app/config.py`** `Settings`(app_env·log_level·log_json·metrics_enabled·debug) +
  `get_settings()`(캐시)·`reload_settings()`·`resolve_env()` _(요구사항 1·4)_. `_DEFAULTS`로 환경별 기본,
  `_flag`/`os.getenv`로 명시 우선.
- **`bff/gateway/config.py`** `APP_ENV`·`BE_BASE_URL`·`UPSTREAM_TIMEOUT`·`LOG_JSON`·`IS_PROD` — 환경
  기본 + 명시 우선(기존 상수명 유지) _(요구사항 2)_.
- **`frontend/src/config/index.ts`** `resolveAppEnv()`(VITE_APP_ENV>MODE>dev)·`APP_ENV`·`config`
  _(요구사항 2)_.
- **`backend/app/platform/wiring.py`** `register_middleware/startup/shutdown`(priority) + `apply(app)` +
  `_reset()`(테스트) _(요구사항 3)_. `internal.py`가 `wiring.apply(app)` 1회 호출.

## 데이터 모델 / 계약
- 신규 계약 없음(런타임 구성). `Settings`는 내부 타입.

## 에러 처리
- 미지 `APP_ENV` → dev 폴백(예외 없음). 명시 env 파싱은 불리언 헬퍼로 관대하게.

## 테스트 전략
- `backend/tests/test_config.py` — 환경별 기본(1-1)·명시 우선(1-2)·폴백(1-3)·reload(4-1)·wiring
  register/apply/무동작(3-1·3-2).
- `frontend/.../config.test.ts` — resolveAppEnv 우선순위.
- 회귀 — 전 스위트 green(기존 동작 불변).

## 설계 결정
- 추가형(스트랭글러) — 전면 마이그레이션 대신 공존, 점진 채택(ADR-0056).
- 배선은 priority 정렬 append-only — 병렬 스트림 충돌 회피.

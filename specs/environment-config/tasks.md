# 작업 (Tasks) — 환경 계층 & 구성 토대

- [x] 1. ADR-0056 + 인덱스 + `docs/production-readiness.md` 추적 매트릭스 _(요구사항 1~4)_
- [x] 2. `backend/app/config.py` — Settings·get/reload·resolve_env _(요구사항 1·4)_
- [x] 3. `backend/app/platform/wiring.py`(+`__init__`) + `internal.py` apply 배선 _(요구사항 3)_
- [x] 4. `bff/gateway/config.py` 환경화 + `frontend/src/config/index.ts` _(요구사항 2)_
- [x] 5. `.env.example`에 APP_ENV·LOG_* 문서화 _(요구사항 1)_
- [x] 6. 테스트 — backend test_config.py + frontend config.test.ts, 전 스위트 green·ruff/eslint _(요구사항 1~4)_

## 진행 메모
- 추가형(회귀 불변). 0053~0055는 동시 스트림 점유 → 본 토대는 0056.
- 이후 웨이브 스트림은 `config`/`wiring` 위에 등록만으로 얹는다.

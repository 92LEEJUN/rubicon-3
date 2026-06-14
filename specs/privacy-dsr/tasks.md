# 작업 (Tasks) — 개인정보/규제(Privacy·DSR)

> `design.md` 를 실제 구현으로 나눈 체크리스트. 끝에 관련 요구사항 번호를 표기한다.

## 작업 목록

- [x] 1. ADR-0061 작성(결정·후보안·기각·영향) _(요구사항 전체)_
- [x] 2. specs 3종(requirements·design·tasks) _(요구사항 전체)_
- [x] 3. `backend/app/privacy/` 패키지 생성 _(요구사항 7)_
  - [x] 3.1 `consent.py` — `KNOWN_SCOPES`·`ConsentStore`(grant/revoke/status, unknown→ValueError) _(요구사항 1)_
  - [x] 3.2 `dsr.py` — `DSRService`(export/delete/rectify, user_id 키 집계·best-effort 삭제) _(요구사항 2, 3, 4)_
  - [x] 3.3 `retention.py` — `RETENTION_DAYS`·`RetentionPolicy`(policy/sweep Mock) _(요구사항 5)_
  - [x] 3.4 `audit.py` — `AuditEvent`·`AuditLog`(record/list, 비차단) _(요구사항 6)_
  - [x] 3.5 `router.py` — DSR `APIRouter` + 엔드포인트 + `wiring.register_router` _(요구사항 7)_
  - [x] 3.6 `__init__.py` — 공개 심볼 export _(요구사항 7)_
- [x] 4. `backend/app/platform/registry.py`에 import 한 줄 append(`# noqa: F401`)로 라우터 로드 _(요구사항 7)_
- [x] 5. `backend/tests/test_privacy.py` — 단위·통합·회귀(접근·삭제·동의 철회) _(요구사항 1~7)_
- [x] 6. 검증: `ruff check backend/` 클린 · `python -m pytest` 전부 green _(요구사항 7)_

## 진행 메모
- DSR 라우터는 `api/internal.py`의 모듈-수준 `_container`·`_users`를 lazy import로 공유한다
  (별도 컨테이너 생성 시 상태가 갈라져 접근/삭제가 무의미해짐).
- 만료 스윕은 Mock(후보 보고·비변형). 실 삭제는 후속 S5 확장에서 retention 어댑터로 배선.
- 동의 모델(User.consent)은 ADR-0030 유지 — ConsentStore는 그 위의 부여/철회 헬퍼.

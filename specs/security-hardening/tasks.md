# 작업 (Tasks) — S7 보안 심화

> `design.md`를 구현으로 나눈 체크리스트. 끝에 요구사항 번호 표기.

## 작업 목록

- [x] 1. 스펙 3종 + ADR-0063 작성 _(요구사항 1~6)_
  - requirements / design / tasks + `docs/adr/0063-security-hardening.md`
- [x] 2. 입력 검증 유틸 `backend/app/security/validation.py` _(요구사항 3)_
  - [x] 2.1 `ValidationError` + `check_payload_size` (크기 상한)
  - [x] 2.2 `whitelist_fields` (strip/strict 모드)
- [x] 3. 보안 감사 헬퍼 `backend/app/security/audit.py` _(요구사항 4)_
  - [x] 3.1 S5 `AuditLog.record` 재사용 위임 + `security.*` 정규화
  - [x] 3.2 액션 상수(RATELIMIT_BLOCK·AUTH_FAILURE·COMMIT_GATE), 시그니처 불변
- [x] 4. 레이트리밋 `bff/gateway/ratelimit.py` _(요구사항 1)_
  - [x] 4.1 `TokenBucket`·`RateLimiter`·`client_key`
  - [x] 4.2 `install_ratelimit` 미들웨어(토글 게이트·429·Retry-After·감사 기록)
- [x] 5. 보안 헤더 `bff/gateway/security.py` _(요구사항 2)_
  - [x] 5.1 `install_security_headers`(추가형·토글 게이트)
  - [x] 5.2 `install_security` 통합 시임
- [x] 6. 앱 팩토리 배선 — `gateway/main.py`에 `install_security(app)` 한 줄(토글 off=무동작) _(요구사항 6)_
- [x] 7. 의존성 스캔 워크플로 `.github/workflows/security.yml`(신규 파일만) _(요구사항 5)_
- [x] 8. 테스트 — bff(ratelimit·headers)·backend(validation·audit) _(요구사항 1~4)_
- [x] 9. 검증 — ruff 클린·backend/bff pytest green·토글 off 회귀 불변 _(요구사항 6)_

## 진행 메모
- 레이트리밋 미들웨어는 관측성(`install_observability`)과 동형으로 앱 팩토리에서 `install_security(app)`
  한 줄로 등록. 토글 off면 미들웨어 자체를 등록하지 않아 오버헤드 0(회귀 불변).
- 감사는 S5 `backend/app/privacy/audit.py`의 `AuditLog`를 import해 재사용. 새 sink/시그니처 없음.
- BFF에서 backend 감사 헬퍼를 쓸 때는 pytest pythonpath(`. ../backend`)로 `app.security.audit` import 가능.
  미들웨어는 audit가 None이면 감사를 건너뛴다(선택적 의존).

# 설계 (Design) — 개인정보/규제(Privacy·DSR)

> `requirements.md` 의 요구사항을 **어떻게** 만족시킬지 설명한다.
> 기반 문서 참조: `docs/adr/0030-consent-scoped.md`(scope 모델), `docs/adr/0029-engagement-vs-analytics.md`,
> `docs/data-model.md` §3(Consent·User), `docs/production-readiness.md` S5, `docs/adr/0061-privacy-dsr.md`.

## 개요
신규 패키지 `backend/app/privacy/`에 **동의 확장·DSR 서비스·보존 정책·감사 훅**을 모은다.
엔드포인트는 신규 `APIRouter`로 만들어 `wiring.register_router`로 등록하고,
`platform/registry.py`에 import 한 줄(append, `# noqa: F401`)을 더해 로드한다.
앱 팩토리(`api/internal.py`)는 **편집하지 않는다**(병렬 충돌 회피, ADR-0056).
기존 `user_id` 키잉 Repository를 **재사용**해 데이터를 모으고/지운다(시그니처 불변, 추가형).

## 아키텍처
```
[DSR Router]  /internal/privacy/*
     │  (Depends → 공유 _container · _users)
     ├── ConsentStore  : User.consent(scopes) 부여/철회/조회        (요구 1)
     ├── DSRService     : access/export · delete · rectify          (요구 2·3·4)
     │       └─ 집계/삭제 대상: order · conversation_memory · open_loops · engagement
     ├── RetentionPolicy: 카테고리별 보존기한 + Mock 만료 스윕        (요구 5)
     └── AuditLog       : 보안 의미 이벤트 기록(비차단)               (요구 6)
```
- 라우터는 `api/internal.py`의 모듈-수준 `_container`·`_users`를 **lazy import**해 동일 상태를 공유한다
  (별도 컨테이너를 만들면 상태가 갈라져 접근/삭제가 무의미해짐).

## 주요 컴포넌트 / 인터페이스

- **`consent.py` — `KNOWN_SCOPES`·`ConsentStore`**: `User.consent.scopes`(ADR-0030)를 부여/철회.
  - `grant(user, scope) -> Consent` / `revoke(user, scope) -> Consent` / `status(user) -> dict[str,bool]`
  - 알 수 없는 scope는 `ValueError`(라우터가 400 매핑). `UserDirectory.upsert`로 프로필 반영. _(요구 1)_

- **`dsr.py` — `DSRService`**: 컨테이너를 받아 user_id로 데이터 집계/삭제/정정.
  - `export(user_id) -> dict`: 프로필·동의·orders·conversation_memory·open_loops·engagement를
    JSON 직렬화 가능한 dict로 모은다. 없으면 빈 컬렉션(형태 보존). _(요구 2)_
  - `delete(user_id) -> dict`: 각 저장소의 삭제 메서드(`delete`/`clear`/`delete_user`/`reassign_user`
    부재 시 skip)로 best-effort 삭제, 저장소별 결과 요약 반환. _(요구 3)_
  - `rectify(user_id, fields) -> User`: `_RECTIFIABLE`(display_name·addresses·preferences) 허용 필드만
    갱신. 허용 외 필드는 `ValueError`. _(요구 4)_

- **`retention.py` — `RetentionPolicy`**: 카테고리별 보존기한(일) 상수 + Mock 스윕.
  - `policy() -> dict[str,int]` / `sweep(now=None) -> dict[str,int]`(Mock=후보 0건 보고, 비변형). _(요구 5)_

- **`audit.py` — `AuditEvent`·`AuditLog`**: 인메모리 sink(인터페이스).
  - `record(action, subject, detail=None)` / `list() -> list[AuditEvent]`. sink 실패는 삼킨다(비차단). _(요구 6)_

- **`router.py` — `router: APIRouter`**: 아래 엔드포인트. 모듈 import 시 `wiring.register_router(router)`. _(요구 7)_

## 데이터 모델
- 신규 도메인 타입 **불필요**(Consent·User 재사용). 감사 이벤트는 dataclass(`AuditEvent`)로 패키지 내부.
- 보존 정책은 모듈 상수 `RETENTION_DAYS`(카테고리→일).

## 엔드포인트(신규, 모두 `/internal/privacy` 프리픽스)
| 메서드·경로 | 책임 | 요구 |
|---|---|---|
| `GET  /internal/privacy/consent` | scope별 동의 상태 | 1 |
| `POST /internal/privacy/consent/grant` | scope 부여(body: `{scope}`) | 1 |
| `POST /internal/privacy/consent/revoke` | scope 철회(body: `{scope}`) | 1 |
| `GET  /internal/privacy/dsr/export` | 접근/내보내기 | 2 |
| `POST /internal/privacy/dsr/delete` | 삭제(잊힐 권리) | 3 |
| `POST /internal/privacy/dsr/rectify` | 정정(body: 허용 필드) | 4 |
| `GET  /internal/privacy/retention/policy` | 보존 정책 | 5 |
| `POST /internal/privacy/retention/sweep` | Mock 만료 스윕 | 5 |
| `GET  /internal/privacy/audit` | 감사 로그 | 6 |

- 신원은 기존 패턴과 동일하게 헤더(`X-User-Id`/`X-Guest-Token`) → Principal → user_id로 해석한다.

## 에러 처리
- 알 수 없는 scope·정정 불가 필드 → **400**(JSONResponse, `code`/`message`).
- 삭제 시 저장소가 삭제 메서드 미제공 → skip(요약에 `skipped` 표기), 흐름 비차단.
- 감사 sink 실패 → 삼킴(주 흐름 비차단).

## 테스트 전략 (`backend/tests/test_privacy.py`)
- **단위**: ConsentStore grant/revoke/status·unknown scope, DSRService export/delete/rectify,
  RetentionPolicy policy/sweep, AuditLog record/list.
- **통합(TestClient)**: consent grant→status, dsr export(형태)·delete(후속 export 빈 결과)·
  consent revoke(다른 scope 보존). 감사 로그가 동의/DSR 이벤트를 담는지.
- **회귀**: 기존 스위트 전부 green(라우터 등록이 기존 엔드포인트를 깨지 않음).

## 설계 결정 / 대안
- **공유 컨테이너 재사용 vs 신규 컨테이너**: 재사용 선택. DSR은 *실제 보관 데이터*에 작동해야
  의미가 있으므로 `internal.py`의 모듈 상태를 lazy import로 공유한다.
- **Consent를 별도 저장소로 분리 vs User에 유지**: User.consent 유지(ADR-0030 모델 보존, 추가형).
  ConsentStore는 그 위의 부여/철회 헬퍼일 뿐 새 스키마를 만들지 않는다.
- **만료 스윕 실제 삭제 vs Mock 보고**: Mock 보고 선택(회귀 불변·외부 인프라 어댑터 허용, DoD).

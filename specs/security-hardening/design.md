# 설계 (Design) — S7 보안 심화

> `requirements.md`의 요구사항을 **어떻게** 만족시킬지. 기반 결정은 [ADR-0063](../../docs/adr/0063-security-hardening.md),
> 가드레일 계층 분담은 [ADR-0052](../../docs/adr/0052-guardrail-agent.md)(에지=레이트리밋, 내용검사=오케스트레이터),
> 감사 재사용은 [ADR-0061](../../docs/adr/0061-privacy-dsr.md)을 따른다.

## 개요
S7은 **에지(BFF) 친화 보안 검사**(레이트리밋·보안 헤더)와 **재사용 가능한 입력 검증 유틸**,
**감사 강화**(S5 재사용), **의존성 스캔 CI**로 구성된다. 모든 신규 동작은 토글 뒤(`RATE_LIMIT`·
`SECURITY_HEADERS`)이며 기본 off면 회귀 불변(요구사항 6). ADR-0052의 계층 분담대로 레이트리밋은
에지(BFF)가 소유하고, 내용 검사(PII·인젝션)는 본 스트림 범위가 아니다(오케스트레이터 가드레일).

## 아키텍처
```
            FastAPI BFF (gateway/main.py)
  ┌──────────────────────────────────────────────┐
  │  install_security(app)  (옵트인, 토글 게이트)   │
  │   ├─ @middleware http: ratelimit (RATE_LIMIT)  │ → 429 {RateLimited} + Retry-After
  │   └─ @middleware http: security headers        │ → 추가형 헤더(SECURITY_HEADERS)
  └──────────────────────────────────────────────┘
                  │ 보안 이벤트
                  ▼
   backend/app/privacy/audit.py  AuditLog.record("security.*", ...)   ← 재사용(요구사항 4)
                  ▲
   backend/app/security/audit.py  security_audit() 헬퍼(추가형, 시그니처 불변)

  backend/app/security/validation.py  ← 순수 유틸(페이로드 크기·필드 화이트리스트, 옵트인)

  .github/workflows/security.yml  ← pip-audit(별도 파일, ci.yml 미편집)
```

미들웨어 등록은 관측성(`install_observability`)과 동형으로 `install_security(app)` 한 줄을 앱 팩토리에서
호출한다. 미들웨어는 토글 off면 **무동작 패스스루**(요청을 그대로 흘려 보냄)이다.

## 주요 컴포넌트 / 인터페이스

- **`bff/gateway/ratelimit.py`**: 토큰버킷 레이트리미터 + ASGI 미들웨어. _(요구사항 1)_
  - `class TokenBucket(rate, capacity)`: `allow() -> (ok, retry_after)`. monotonic 시계 기반 보충.
  - `class RateLimiter(rate, capacity)`: 키별 버킷 맵. `check(key) -> (ok, retry_after)`.
  - `client_key(request) -> str`: `X-User-Id` → `X-Guest-Token` → `request.client.host` 순.
  - `install_ratelimit(app, limiter=None, audit=None)`: 토글 on일 때만 `@app.middleware("http")` 등록.
    차단 시 `JSONResponse(429, {"code":"RateLimited","retry_after":n}, headers={"Retry-After":str(n)})`.
- **`bff/gateway/security.py`**: 보안 헤더 미들웨어 + 통합 설치 헬퍼. _(요구사항 2)_
  - `SECURITY_HEADERS: dict[str,str]` — `X-Content-Type-Options:nosniff`·`X-Frame-Options:DENY`·
    `Referrer-Policy:no-referrer`·`X-XSS-Protection:0`·`Cross-Origin-Opener-Policy:same-origin`.
  - `install_security_headers(app)`: 토글 on일 때만 미들웨어 등록, 없는 헤더만 추가(추가형).
  - `install_security(app, audit=None)`: 위 두 설치 헬퍼를 한 번에 호출(앱 팩토리 시임).
- **`backend/app/security/validation.py`**: 순수 입력 검증 유틸. _(요구사항 3)_
  - `class ValidationError(ValueError)` + 코드(`PayloadTooLarge`·`UnknownField`).
  - `check_payload_size(raw: bytes|str, max_bytes: int)`: 초과 시 `ValidationError`.
  - `whitelist_fields(data: dict, allowed, mode="strip"|"strict")`: strip=미상 키 제거, strict=거부.
- **`backend/app/security/audit.py`**: 보안 감사 헬퍼(S5 재사용). _(요구사항 4)_
  - `security_audit(log: AuditLog, event: str, subject: str, detail=None)`: `AuditLog.record`로 위임.
    `event`를 `security.*` 네임스페이스로 정규화. 기존 시그니처 불변, 추가형.
  - 액션 상수: `RATELIMIT_BLOCK`·`AUTH_FAILURE`·`COMMIT_GATE`.
- **`.github/workflows/security.yml`**: `pip-audit` 의존성 스캔. _(요구사항 5)_

## 데이터 모델
새 영속 스키마 없음. 레이트리밋 상태는 **인메모리 버킷 맵**(프로세스 로컬, 실 전환 시 Redis 어댑터로
교체 — operations Phase B 토폴로지). 감사 이벤트는 기존 `AuditEvent`를 그대로 사용(`action`에
`security.*` 문자열).

## 에러 처리
- 레이트리밋 초과 → `429`(차단), 그 외 정상 통과. 미들웨어 내부 예외는 삼키고 통과(보안 미들웨어가
  서비스를 깨지 않음 — 가용성 우선).
- 입력 검증 유틸은 `ValidationError`를 raise하며, 호출부가 `400`으로 매핑(옵트인이므로 기본 경로 불변).
- 감사 sink 실패는 기존 `AuditLog.record`가 삼킴(비차단, 요구사항 4.3).

## 테스트 전략
- `bff/tests/test_ratelimit.py`: 토큰버킷 보충·키 식별·429+Retry-After·토글 off 무동작.
- `bff/tests/test_security_headers.py`: 토글 on 추가/off 무동작/기존 헤더 비덮어쓰기.
- `backend/tests/test_security_validation.py`: 크기 초과·화이트리스트 strip/strict·정상 통과.
- `backend/tests/test_security_audit.py`: `security.*` 기록·S5 AuditLog 재사용·시그니처 불변.
- 회귀: 토글 off에서 기존 BFF/백엔드 스위트 green 유지(요구사항 6).

## 설계 결정 / 대안
- **토큰버킷 vs 슬라이딩윈도우**: 토큰버킷 채택(버스트 허용·O(1)·stdlib monotonic만 필요). ADR-0063 참조.
- **에지 소유**: ADR-0052 부분 채택대로 레이트리밋은 BFF 에지가 소유(내용 검사는 오케스트레이터).
- **감사 재사용**: 새 sink를 만들지 않고 S5 `AuditLog`에 `security.*` action으로 기록(ADR-0061 확장 경로).
- **인메모리 버킷**: 단일 프로세스 가정(MVP). 멀티 인스턴스는 Redis 어댑터(후속, operations Phase B).

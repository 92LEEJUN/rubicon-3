# 요구사항 (Requirements) — S7 보안 심화(Security Hardening)

## 개요
프로덕션 준비도 S7(보안 심화, Well-Architected 보안·OWASP)의 갭을 채운다. BFF 에지에 **레이트리밋/남용
방지·보안 응답 헤더**를 더하고, **입력 검증 하드닝**(페이로드 크기·필드 화이트리스트) 유틸을 제공하며,
S5(`backend/app/privacy/audit.py`)의 `AuditLog`를 **재사용·확장**해 보안 의미 이벤트(레이트리밋 차단·
인증 실패·커밋 게이트)를 기록한다. 또한 **의존성 취약점 스캔** 워크플로(`.github/workflows/security.yml`)를
추가한다. 모든 신규 동작은 토글 뒤에 두고 **기본 off = 회귀 불변**(스트랭글러)을 지킨다.

## 요구사항 목록

### 요구사항 1: 레이트리밋 / 남용 방지(BFF 에지)

**User Story:**
운영자로서, 클라이언트별(신원/IP) 요청 속도를 제한하기를 원한다, 그래서 남용·폭주로부터 백엔드를
보호할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN `RATE_LIMIT` 토글이 off(기본)일 때 THEN 시스템은 레이트리밋을 적용하지 않아야 한다 (회귀 불변) (SHALL).
2. WHEN `RATE_LIMIT`이 on이고 한 키(신원 또는 IP)의 요청이 윈도우 내 허용치를 초과하면 THEN 시스템은
   `429`와 표준 본문(`{code:"RateLimited", retry_after}`)을 반환해야 한다 (SHALL).
3. WHEN 키가 식별될 때 THEN 시스템은 신원(X-User-Id/X-Guest-Token) 우선, 없으면 클라이언트 IP를 키로
   사용해야 한다 (SHALL).
4. WHILE 레이트리밋이 활성일 때 시스템은 차단 응답에 `Retry-After` 헤더를 포함해야 한다 (SHALL).
5. WHEN 토큰버킷이 시간 경과로 보충되면 THEN 시스템은 다시 요청을 허용해야 한다 (SHALL).

### 요구사항 2: 보안 응답 헤더(추가형)

**User Story:**
보안 담당자로서, 표준 보안 응답 헤더가 모든 응답에 실리기를 원한다, 그래서 브라우저 측 흔한 공격면
(클릭재킹·MIME 스니핑 등)을 줄일 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN `SECURITY_HEADERS` 토글이 off(기본)일 때 THEN 시스템은 헤더를 추가하지 않아야 한다 (회귀 불변) (SHALL).
2. WHEN 토글이 on일 때 THEN 시스템은 `X-Content-Type-Options`·`X-Frame-Options`·`Referrer-Policy` 등
   표준 보안 헤더를 응답에 **추가**해야 한다 (기존 헤더/본문 불변) (SHALL).
3. IF 응답에 이미 같은 헤더가 있으면 THEN 시스템은 덮어쓰지 않아야 한다 (추가형) (SHALL).

### 요구사항 3: 입력 검증 하드닝(가드 유틸)

**User Story:**
개발자로서, 페이로드 크기·필드 화이트리스트를 검증하는 재사용 유틸을 원한다, 그래서 과대 입력·미상
필드 주입을 경계에서 막을 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 페이로드 바이트 크기가 상한을 초과하면 THEN 유틸은 검증 오류(`PayloadTooLarge`)를 발생시켜야 한다 (SHALL).
2. WHEN dict 입력에 화이트리스트 밖 키가 있으면 THEN 유틸은 해당 키를 거부하거나(strict) 제거(strip)할 수
   있어야 한다 (SHALL).
3. WHEN 입력이 유효하면 THEN 유틸은 정제된 값을 그대로(또는 화이트리스트만 남겨) 반환해야 한다 (SHALL).
4. WHILE 유틸이 순수 함수로 동작할 때 시스템은 어떤 전역 상태도 변경하지 않아야 한다 (결정적·테스트 가능) (SHALL).

### 요구사항 4: 감사 로그 강화(S5 재사용·확장)

**User Story:**
보안 담당자로서, 보안 의미 이벤트(레이트리밋 차단·인증 실패·커밋 게이트)가 감사 로그에 남기를 원한다,
그래서 남용·접근 시도를 사후 추적할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 보안 이벤트가 발생하면 THEN 시스템은 S5 `AuditLog.record(action, subject, detail)`를 **재사용**해
   기록해야 한다 (중복 구현 금지) (SHALL).
2. WHEN 보안 이벤트 action 명을 지을 때 THEN 시스템은 `security.*` 네임스페이스
   (`security.ratelimit_block`·`security.auth_failure`·`security.commit_gate`)를 사용해야 한다 (SHALL).
3. IF sink 기록이 실패해도 THEN 시스템은 주 흐름을 막지 않아야 한다 (비차단; 기존 AuditLog 계약 유지) (SHALL).
4. WHILE 확장이 필요할 때 시스템은 기존 `AuditEvent`/`AuditLog` 시그니처를 **변경하지 않고**(추가형)
   헬퍼만 더해야 한다 (SHALL).

### 요구사항 5: 의존성 취약점 스캔(CI 워크플로)

**User Story:**
딜리버리 담당자로서, 의존성 취약점을 CI에서 스캔하기를 원한다, 그래서 알려진 CVE를 가진 패키지를 조기에
발견할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 보안 워크플로를 추가할 때 THEN 시스템은 기존 `.github/workflows/ci.yml`을 편집하지 않고 **신규
   파일** `.github/workflows/security.yml`만 추가해야 한다 (S9 소유 경계) (SHALL).
2. WHEN 워크플로가 실행되면 THEN 시스템은 backend·bff requirements에 대해 `pip-audit`(CI 단계 설치형)
   스캔을 수행해야 한다 (SHALL).
3. IF 새 무거운 런타임 의존성이 필요하면 THEN 시스템은 이를 추가하지 않고 stdlib/기존 의존성만 사용해야
   한다 (스캐너는 CI 단계에서만 설치) (SHALL).

### 요구사항 6: 회귀 불변·토글

**User Story:**
유지보수자로서, 모든 신규 보안 기능이 토글 뒤에 있기를 원한다, 그래서 토글 off면 오늘과 동일하게
동작함을 보장할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 모든 보안 토글(`RATE_LIMIT`·`SECURITY_HEADERS`)이 off(기본)일 때 THEN 시스템은 기존 BFF 동작과
   동일해야 한다 (SHALL).
2. WHEN 입력 검증 유틸이 호출되지 않으면 THEN 시스템은 어떤 엔드포인트 동작도 바꾸지 않아야 한다 (옵트인) (SHALL).

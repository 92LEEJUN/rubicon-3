# ADR-0063: 보안 심화(S7) — 에지 레이트리밋 + 추가형 보안 헤더 + 감사 재사용

- **상태**: 채택
- **관련**: `docs/production-readiness.md` S7, `docs/adr/0052-guardrail-agent.md`(계층 분담: 에지=레이트리밋·
  내용검사=오케스트레이터), `docs/adr/0061-privacy-dsr.md`(감사 AuditLog), `docs/adr/0056-environment-config-baseline.md`
  (토글·env), `docs/operations.md`(남용 방지·Phase B 토폴로지), `specs/security-hardening/`,
  `bff/gateway/{ratelimit,security}.py`, `backend/app/security/*`

## 배경
프로덕션 준비도 S7(보안 심화, Well-Architected 보안·OWASP)이 비어 있다(⬜). 에지 친화 검사(레이트리밋·
남용 방지)·표준 보안 응답 헤더·입력 검증 하드닝·보안 의미 감사·의존성 취약점 스캔이 필요하다. ADR-0052는
이미 신뢰·안전을 **계층 분담**으로 결정했다 — **에지 친화 검사(레이트리밋, R1)는 BFF/에지가 소유**,
내용 검사(PII·인젝션·콘텐츠 정책)는 오케스트레이터 가드레일이 소유(부분 채택). S7은 그 중 **에지 절반**과
**횡단 유틸·감사·CI 스캔**을 구현한다. S5(ADR-0061)는 이미 인메모리 `AuditLog`를 두고 "실 sink·확장은
후속 S7에서"라 명시했다.

## 후보안
| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| A | 레이트리밋을 BE 도메인 미들웨어로 | BE 일관 | 에지 보호가 늦음·BFF가 첫 방어선인데 통과시킴 |
| B | 보안 검사를 엔드포인트마다 인라인 | 국소 | 흩어짐·드리프트(ADR-0052가 이미 기각한 안티패턴) |
| **C (선택)** | **BFF 에지 미들웨어(레이트리밋·헤더) + 재사용 유틸 + S5 감사 재사용 + 별도 CI** | 첫 방어선·횡단 일관·중복 0·토글 회귀 불변 | 인메모리 버킷은 멀티 인스턴스에 Redis 어댑터 필요(후속) |

## 결정
**C.**
- **레이트리밋은 BFF 에지가 소유**(ADR-0052 분담). `bff/gateway/ratelimit.py`에 **토큰버킷** 기반
  `RateLimiter` + ASGI 미들웨어. 키는 **신원 우선**(X-User-Id → X-Guest-Token) → 없으면 클라이언트 IP.
  초과 시 `429 {code:"RateLimited", retry_after}` + `Retry-After` 헤더.
- **보안 헤더는 추가형**. `bff/gateway/security.py`가 표준 보안 헤더(X-Content-Type-Options·X-Frame-Options·
  Referrer-Policy 등)를 응답에 **추가**(이미 있으면 비덮어쓰기). 본문·기존 헤더 불변.
- **입력 검증은 순수 유틸**. `backend/app/security/validation.py`(페이로드 크기·필드 화이트리스트)는
  **옵트인**(호출 안 하면 동작 불변). 전역 상태 미변경.
- **감사는 S5 재사용**. `backend/app/security/audit.py`는 S5 `AuditLog.record`로 **위임**만 한다
  (`security.ratelimit_block`·`security.auth_failure`·`security.commit_gate`). 새 sink·새 시그니처
  **금지**(ADR-0061 AuditLog 계약 불변, 추가형 헬퍼만).
- **의존성 스캔은 별도 워크플로**. `.github/workflows/security.yml`(신규 파일)에서 `pip-audit`로 backend·
  bff requirements 스캔. **`ci.yml`은 편집하지 않는다**(S9 소유).
- **회귀 불변·토글**. `RATE_LIMIT`·`SECURITY_HEADERS` 기본 off → 미들웨어 미등록 = 오늘과 동일(스트랭글러).
  새 무거운 런타임 의존성 없음(stdlib만; pip-audit는 CI 단계 설치).

## 기각 이유
- **A**: BFF가 첫 방어선인데 BE까지 요청을 흘려 보내면 에지 보호 의미가 약하다. 레이트리밋은 에지에서.
- **B**: 인라인은 흩어짐·드리프트로 ADR-0052가 이미 기각한 안티패턴. 횡단 관심사는 한 경계(미들웨어)에.

## 결과/영향
- 기본 동작 불변(추가형·토글 off). 미들웨어는 관측성(`install_observability`)과 동형으로 앱 팩토리에서
  `install_security(app)` 한 줄로 등록. 토글 off면 미들웨어 자체를 달지 않아 오버헤드 0.
- 인메모리 버킷은 단일 프로세스 가정(MVP). **멀티 인스턴스 정합은 Redis 어댑터**(후속, operations Phase B
  토폴로지). 실 감사 sink(DB·로그 집계)도 후속 어댑터.
- 통합 주의: 토글 `RATE_LIMIT`·`SECURITY_HEADERS`(기본 off), BFF 미들웨어는 `install_security(app)`로 등록,
  감사는 S5 `app.privacy.audit.AuditLog`를 import 재사용(시그니처 불변).

# 설계 (Design) — 멀티테넌트 상태 + 영속화

> [requirements.md](./requirements.md)를 어떻게 만족시킬지 설계한다. 기반 문서
> [operations.md](../../docs/operations.md)(동시성·세션 격리·상태 격리)·[data-model.md](../../docs/data-model.md)
> (Repository/Port 타입)·[api-contract.md](../../docs/api-contract.md) §2.4(내부 API·BFF 신뢰)를 참조한다.
> 공유 데이터 모델·아키텍처가 바뀌면 본 design이 아니라 기반 문서를 갱신하고 여기서 참조한다.

## 1. 개요
단일 User가 박힌 전역 컨테이너를, **요청별 Principal로 해석되는 상태 범위**로 바꾼다. 무상태
참조 서비스는 싱글턴으로 공유하고, 사용자별 상태는 Principal로 키잉해 격리·영속(DB)한다.
로그인·비로그인(게스트)을 같은 메커니즘으로 다루되 게스트는 커밋 전 로그인을 요구한다. 전환은
스트랭글러(어댑터 교체·토글)로 회귀 없이 진행한다.

## 2. 격리 모델 결정 — A vs B (요구사항 1·3·4·7)

| 기준 | A: 사용자별 컨테이너 레지스트리 | B: 공유 무상태 + 사용자별 상태 |
|---|---|---|
| 변경량 | 적음(진입에서 컨테이너 resolve) | 중간(상태 리포 키잉·진입 배선) |
| 참조데이터(R3) | ❌ 사용자마다 catalog/knowledge 중복 | ✅ 단일 공유 |
| DB 영속(R4) | ❌ "사용자별 컨테이너"는 DB와 부정합(결국 DB 위 캐시) | ✅ user_id 키 테이블에 자연 매핑 |
| 메모리/일관성 | 사용자 수에 비례 중복·동기화 위험 | 참조 1벌 |
| 기존 자산 정합 | 보통 | ✅ `order.checkout(user_id)`·`companion.record_turn(user_id)` 이미 user_id 수용 |
| 게스트(R2) | 게스트마다 컨테이너 → 누수 위험 | ✅ 게스트도 동일 키잉 |

**결정: B.** 사용자가 **DB 영속**을 택했으므로 A는 종단 상태로 부적합하다(참조데이터 중복 R3 위반,
DB와 부정합 R4). B는 무상태/상태를 분리해 DB 키잉과 자연히 맞고, 이미 일부 리포가 user_id를
받는 현 구조와 정합한다. _A는 'DB 없는 순수 인메모리' 범위였다면 변경 최소로 매력적이었으나 본
작업 범위(DB)에서 탈락._ (요구사항 1·3·4)

## 3. Principal & 신원 해석 (요구사항 2 — 로그인/비로그인)

```
Principal = (kind: "user" | "guest", id: str)
  - user :  id = 검증된 user_id (BFF 인증)
  - guest:  id = "guest:<guest_token>"  (핸드셰이크/쿠키 토큰, 없으면 발급)
```

- **해석 규칙**(요청 진입):
  1. user_id 운반 → `Principal(user, user_id)`.
  2. 없음 + guest_token 운반 → `Principal(guest, "guest:"+token)`.
  3. 둘 다 없음 → 새 guest_token 발급 → `Principal(guest, …)` (응답으로 토큰 반환, 이후 재사용).
- **주입 위치**: WS `/internal/turn`은 **핸드셰이크(첫 메시지 또는 쿼리)** 에서 user_id/guest_token 수신;
  HTTP는 헤더 `X-User-Id`/`X-Guest-Token`(또는 본문). 기존 본문 `user_id` 필드와 호환.
- **게스트 정책**(요구사항 2-3·2-4):
  - 게스트는 **조언형 capability(진단·추천·설명·보증조회·상태)** 전부 사용 가능.
  - **커밋(주문·예약)** 은 게스트 차단 — 초안 + `로그인 후 확정` CTA(kind=`login`). 엔드포인트는 401/게이트.
  - **로그인 머지**: `guest:<token>` 상태(장바구니 초안·대화 맥락)를 user_id로 이관하는 `merge(guest_id → user_id)` — **후속 증분**(엔드포인트 `POST /internal/principal/merge`).
- **회귀 보존**(요구사항 7): 토글 off거나 user_id 미지정·게스트 비활성 모드면 **명시적 기본 사용자**(`usr_01`)로 폴백 → 오늘과 동일.

## 4. 주요 컴포넌트 / 인터페이스

```
RequestPrincipal(request) ─► Principal           # FastAPI 의존성(헤더/핸드셰이크 해석)
StateScope(principal)      ─► 사용자범위 접근자    # principal로 키잉된 상태 리포 묶음
AppContext                                        # 공유 무상태 서비스(싱글턴) + StateScope 팩토리
```

- **공유 무상태(싱글턴)**: catalog·knowledge·store·triage·handoff(슬롯 카탈로그). 참조데이터(R3).
- **사용자별 상태(Principal 키)**: order·companion(conversation_memory·open_loops)·engagement·
  notification·**device 소유권**·**user 프로필**. 기존 Repository/Port 시그니처에 user_id 추가/이미 수용.
- **AppContext**: 모듈 1회 구성. `scope(principal)` 호출로 그 사용자의 상태 접근자 반환.
  `internal.py`의 `_container.user`/`_container.<state>` 직접참조를 **`ctx.scope(principal).<state>`** 로 치환.
- **오케스트레이터**: `build_turn(message, principal, session_id)` — 블랙보드는 session_id(요구사항 6),
  도메인 상태는 principal로. 핸들러는 `ctx`에서 user를 principal로 받는다(현 `self.c.user` 제거).

## 5. 데이터 모델 / 영속 (요구사항 4·6)

- **상태 테이블(principal_id 키)**: `orders`·`conversation_memory`·`open_loops`·`engagement`·
  `device_ownership`·`user_profile`. 컬럼은 [data-model.md](../../docs/data-model.md) 타입을 그대로 직렬화.
- **게스트 행**: `principal_id="guest:…"` + `expires_at`(TTL) — 정리 잡으로 만료 회수.
- **공유 참조(키 없음)**: products·cs_knowledge·stores·slots — 시드 데이터, 읽기 전용.
- **어댑터 교체(스트랭글러)**: 기존 `InMemory*Repository`와 동일 Port를 구현하는 **DB 어댑터**(권장:
  SQLModel/SQLite, 기본값) 추가. `PERSISTENCE=memory|db` env 토글. 인터페이스 불변(요구사항 4-2).
- **세션 블랙보드**: 도메인과 별개로 session_id 키. 영속 선택(현 인메모리 유지 가능, 경계 ADR-0049).

## 6. 동시성 (요구사항 5)
- 서빙은 asyncio 단일 루프. 단순 조회/append는 GIL/단일 루프에서 안전.
- **read-modify-write(주문 체크아웃·픽업 전이)**: 임계구역 보호.
  - 인메모리 어댑터: **principal별 `asyncio.Lock`**.
  - DB 어댑터: **트랜잭션**(낙관적 버전 컬럼 또는 `SELECT … FOR UPDATE`).
- 서로 다른 principal은 락 분리로 독립(요구사항 5-2).

## 7. 에러 처리 (요구사항 4-3·7)
- DB 불가 → 5xx/`error` 봉투, 부분 쓰기 없음(트랜잭션 롤백).
- 게스트 커밋 시도 → 401 또는 커밋 게이트(로그인 CTA), 상태 변경 없음.
- principal 해석 실패 → 게스트 폴백(요구사항 2-2) 또는 기본 사용자(토글 off).
- 토글 off(memory·게스트 비활성) → 오늘과 동일 봉투(요구사항 7-1).

## 8. 테스트 전략 (요구사항 7)
- **격리**: 두 principal(userA/userB, guestA/guestB) — A 상태가 B에 안 보임(요구사항 1·2-2).
- **게스트**: user_id 없는 요청 → guest scope; 커밋은 401/로그인 게이트(요구사항 2-3).
- **DB 계약**: 동일 Port 계약 테스트를 memory·DB(SQLite in-memory) **양쪽 파라미터화** 실행(요구사항 4-2).
- **영속**: DB 어댑터에 쓰고 새 인스턴스로 복원(요구사항 4-1).
- **동시성**: 같은 principal 동시 체크아웃 원자성(요구사항 5-1).
- **회귀**: 기본 사용자 전제 기존 테스트 green(요구사항 7-3).

## 9. 이행 순서 (스트랭글러, 요구사항 7)
1. **Principal + 신원 해석(게스트 포함)** — 진입 의존성. 기본 사용자/게스트 폴백으로 회귀 유지.
2. **상태 리포 principal 키잉(인메모리)** — `_container.user`/직접참조 → `ctx.scope(principal)`. 격리 달성.
3. **DB 어댑터 + `PERSISTENCE` 토글** — Port 구현·계약 테스트 양쪽 통과.
4. **동시성** — 인메모리 락 / DB 트랜잭션.
5. **게스트 커밋 게이트** + **게스트→로그인 머지**(후속 증분).

> 각 단계 후 전체 테스트 green 확인(요구사항 7-2). tasks.md에서 위 순서를 체크리스트로 분해한다.

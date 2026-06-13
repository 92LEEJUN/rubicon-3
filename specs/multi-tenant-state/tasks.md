# 작업 (Tasks) — 멀티테넌트 상태 + 영속화

> [design.md](./design.md)를 구현으로 나눈 체크리스트. 전환 = **스트랭글러**(어댑터 교체·토글).
> **불변 원칙:** 매 단계 후 "토글 off(기본 사용자·memory) = 오늘 봉투/동작 동일" 회귀 green 확인.
> DB는 **stdlib `sqlite3`**(의존성 추가 없음)로 구현한다(design §5 권장 SQLModel 대체 — 오프라인 안전).

## 1. Principal + 신원 해석 _(요구사항 2, 7)_ ✅
- [x] 1.1 `Principal(kind, id)` + `default_principal()`·`guest_principal(token)`·`is_guest` (`app/principal.py`).
- [x] 1.2 신원 해석 — `resolve_principal(user_id, guest_token)`. HTTP 본문(`TurnRequest.user_id/guest_token`)·헤더(`X-User-Id`/`X-Guest-Token`)·WS 메시지. 게스트 토큰 없으면 발급.
- [x] 1.3 폴백 — `MULTITENANT` env 토글(기본 off) → 기본 사용자(`usr_01`) 회귀. `UserDirectory`(fixture+게스트 합성).

## 2. 상태 격리 — Principal 키잉(인메모리) _(요구사항 1, 3, 6)_ ✅(턴 경로)
- [x] 2.1 공유 무상태 서비스는 기존 단일 컨테이너 그대로(이미 싱글턴). _리포가 user_id 키잉돼 별도 AppContext 불필요._
- [x] 2.2 상태 리포는 **이미 user_id 키잉**(conversation_memory·open_loop·engagement·order) — 재사용. user 프로필만 `UserDirectory`로 분리.
- [x] 2.3 턴 경로 — `TurnCtx.user`(Principal 사용자), `build_turn/stream_turn/astream(user=)`, capability는 `ctx.user`. `internal.py` 턴 디스패치·`record_turn`·companion이 `principal.id` 사용.
  - [x] 2.3b 잔여 엔드포인트(resume·reengagement(+deliver)·recommendations(+preemptive)·open-loops resolve/dismiss·home·catalog/recommend)도 `X-User-Id`/`X-Guest-Token` 헤더로 principal 스코프. 응답 shape 불변. `test_multitenant_endpoints.py`(8).
- [x] 2.4 테스트 `test_multitenant.py`(8) — Principal 해석·UserDirectory·companion 격리·게스트 채팅 허용·게스트 커밋 401·로그인 주문·토글 off 회귀.

## 3. DB 영속 + 토글 _(요구사항 4)_ ✅(3개 리포)
- [x] 3.1 sqlite 스키마(`app/repositories/sqlite.py`) — `conversation_memory(user_id PK)`·`open_loops(user_id,ref)`·`engagement(user_id,ref)`, 도메인 객체 JSON 직렬화(pydantic). `CREATE TABLE IF NOT EXISTS`.
- [x] 3.2 DB 어댑터 — `Sqlite{ConversationMemory,OpenLoop,Engagement}Repository`(인메모리와 동일 시그니처).
- [x] 3.3 `PERSISTENCE=memory|db` 토글(`container.py`, 시그니처 불변·기본 memory) + 계약 테스트 memory/DB 파라미터화(`test_persistence.py`, 25).
- [x] 3.4 영속 복원 — 파일 sqlite에 쓰고 새 인스턴스로 복원 단언.
  - [ ] 3.5 **order 영속 보류** — `MockOrderAdapter`(stock/place_order)는 `adapters/`라 별도 작업. 후속.

## 4. 동시성 _(요구사항 5)_ ✅
- [x] 4.1 read-modify-write 임계구역 — `KeyedLock`(`app/concurrency.py`, key별 `threading.Lock`)을 OrderService `checkout`(user_id)·`checkout_pickup`(user_id)·`advance_pickup`(order_id)에 적용. 생성자 불변. (DB 트랜잭션은 어댑터 책임.)
- [x] 4.2 동시 체크아웃 원자성 테스트(`test_concurrency.py`, 4) — 계측 어댑터+barrier로 실제 race 재현(잠금 시 무oversell·해제 시 oversell 양방향 입증). GIL 한계 정직 명시.

## 5. 게스트 커밋 게이트 + 머지 _(요구사항 2-3, 2-4)_
- [x] 5.1 게스트 커밋(주문·예약) 차단 — 401 LoginRequired + `login` CTA(slice 1-2에서 구현, `_guest_commit_gate`).
- [ ] 5.2 게스트→로그인 머지 — **문서화만(미구현, 의도적 보류).** 설계는 [design.md](./design.md) §3:
      `merge(guest:<token> → user_id)`로 장바구니 초안·대화 맥락 이관, 엔드포인트 `POST /internal/principal/merge`.
      구현은 별도 증분으로 남긴다(본 작업 범위 외).

## 메모
- 스트랭글러 순서 1→2(격리 달성)→3(영속)→4→5. 각 단계 독립 커밋·회귀 green.
- 기존 자산 재사용: `order.checkout(user_id)`·`companion.record_turn(user_id)`는 이미 user_id 수용 → 키잉 재사용.

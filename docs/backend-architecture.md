# 백엔드 아키텍처 — 기여자 오리엔테이션 가이드

> `backend/`에서 작업을 시작하는 기여자를 위한 **출발점**이다. 무엇이 어디에 있고,
> 핵심 흐름이 어떻게 동작하며, BFF/FE와 어떻게 연결되고, 현재 상태·후속이 무엇인지 안내한다.
>
> **이 문서는 길잡이(navigational)다. 진실의 출처(SoT)는 재서술하지 않는다** — 데이터 모델 필드는
> `docs/data-model.md`, 엔드포인트 스펙은 `docs/api-contract.md`, 결정 근거는 `docs/adr/*`,
> 오케스트레이터 내부는 `docs/orchestration.md`·`docs/agents.md`로 위임(링크)한다. (8절 참조)

---

## 1. 책임 경계 — BE가 하는 것 / 안 하는 것

**BE가 하는 것**
- 도메인 로직·오케스트레이션: 자연어 턴 → capability 라우팅·실행 → 응답 섹션(§2.1 봉투) 생성.
- 결정적 도메인 서비스: 기기 상태·진단·추천·주문/픽업·예약·견적·트리아지(`app/services/services.py`).
- 커밋 게이트(R17): 주문/예약은 `confirmed=False`면 `ConfirmationRequired`(409), 게스트는
  `LoginRequired`(401)로 차단.
- 상태 영속·세션 격리: user_id 키잉 Repository(인메모리/sqlite), 세션 블랙보드 멀티턴 carry.
- 신원 해석: BFF가 인증한 신원(Principal)을 신뢰하고 프로필로 해석(`app/principal.py`).
- 컴패니언/재관여/추천 코어(이어가기·선제 알림·개인화).

**BE가 안 하는 것**
- 인증·세션 관리: BFF 책임. 내부 API는 **검증된 신원을 신뢰**한다(`app/api/internal.py` 모듈 docstring,
  api-contract §2.4 — 내부망 전제).
- FE 표현/네비게이션: 템플릿 종류(kind)·CTA 계약만 산출하고 렌더는 FE.
- 실 외부 연동: 현재 전부 Mock 어댑터(`app/adapters/mock.py`). 실 어댑터는 후속(Port 경계만 고정).
- LLM은 **선택적**: 기본 off면 전부 결정적. 토글 on일 때만 라우팅/prose에 LLM 개입(5절).

---

## 2. 구조 맵

### 진입점 / API
| 경로 | 역할 |
|---|---|
| `app/api/internal.py` | **BFF 전용 내부 API**(FastAPI `app`). WS/POST `/internal/turn`(턴 스트림), 커밋(`/internal/orders`·`/internal/bookings`), 결정적 조회(devices·home·stores·quotes), 컴패니언(resume·reengagement·open-loops). 토글·신원·커밋 게이트 디스패치가 모두 여기 모인다. |
| `app/cli.py` | CLI 데모 진입(레거시 tool-loop 구동). |

### 오케스트레이터 (`app/orchestrator/`)
| 모듈 | 핵심 심볼 | 역할 |
|---|---|---|
| `capability.py` | `CapabilityOrchestrator`, `Capability`, `TurnCtx`, `build_registry`, `route`/`aroute`, `stream_turn`/`astream`, `gate_repair_ctas` | **결정적 백본 + 단일 라우터.** capability 레지스트리, 룰 폴백 + LLM 플래너 병합, plan 캐시, 세션 블랙보드, 수리 CTA 게이팅. ※ 옛 `core.Orchestrator`(`core.py`)는 **제거됨** — 이 모듈로 수렴(스트랭글러 §12.3). |
| `planner.py` | `LLMPlanner` (`propose`/`apropose`) | 조언형 capability를 LLM 구조화 출력으로 **선택만** 함(행동형 order는 제외). 주입형, 동기/비동기. |
| `classify.py` | `IntentClassifier`(Protocol), `RuleBasedClassifier`, `OpenAIClassifier`(deprecated) | 키워드 규칙 분류기. ADR-0048 이후 **플래너 미연결·실패 시 폴백**으로만 쓰임. |
| `handlers.py` | `handle_device_status`·`handle_troubleshoot`·`handle_recommend`·`handle_order`·`handle_warranty`·`handle_booking`·`handle_explain`·`handle_general`·`handle_clarify`, `LABELS`, `resolve_part_ids`, `_order_cta` | 의도별 핸들러 — 도메인 서비스 호출 → `MessageSection`(템플릿 kind) 생성. capability `run`이 재사용. |
| `legacy.py` | `astream_turn`, `SYSTEM`, `INTENT_SCHEMA` | LLM tool-loop(자연어 prose) 경로. `LLM_BACKED on, MULTIAGENT off`에서 사용. capability에 LLM agent capability가 생기면 제거 대상(후속). |
| `runtime.py` | `astream_multiagent`, `plan_workers`, `should_review` | 슈퍼바이저-워커 멀티에이전트 스트리밍. `LLM_BACKED on, MULTIAGENT on`에서 사용. 후속 제거 대상. |
| `multiagent.py` | 슈퍼바이저-워커 벤치/지연 계측(런타임 배선 아님). |
| `prompts.py` | 멀티에이전트 프롬프트 단일 출처(ADR-0013). |

### 도메인 / 서비스 / 데이터
| 위치 | 핵심 심볼 | 역할 |
|---|---|---|
| `app/domain/models.py` | `Device`·`Order`·`Quote`·`Booking`·`User`·`MessageSection`·`Template`·`Cta`·`AssistantTurn`·`OpenLoop` 등(필드는 `docs/data-model.md`) | Pydantic 도메인 모델. |
| `app/services/services.py` | `DeviceService`·`KnowledgeService`·`CatalogService`·`OrderService`·`HandoffService`·`NotificationService`·`StoreService`·`TriageService`, `_ORDER_LOCKS` | 결정적 도메인 서비스. `OrderService`가 커밋 게이트(`ConfirmationRequired`)·픽업 전이·`KeyedLock`(user_id/order_id) 직렬화 담당. |
| `app/ports/base.py` | `DevicePort`·`CatalogPort`·`OrderPort`·`HandoffPort`·`WarrantyPort`·`StorePort`·`QuotePort`·`ActionGatePort` 등(Protocol) | Mock↔Real 경계(ADR-0020). |
| `app/adapters/mock.py` | `MockDeviceAdapter`·`MockOrderAdapter`·`MockStoreAdapter`·`MockQuoteAdapter`·`MockAlertAdapter` 등 | 현재 유일한 Port 구현(MVP). |
| `app/repositories/memory.py`·`conversation_memory.py`·`conversation_store.py`·`open_loop.py` | `InMemoryEngagementRepository`·`InMemoryConversationMemoryRepository`·`InMemoryConversationStore`·`InMemoryOpenLoopRepository` | 인메모리 상태 리포(user_id 키잉). |
| `app/repositories/sqlite.py` | `SqliteConversationMemoryRepository`·`SqliteOpenLoopRepository`·`SqliteEngagementRepository` | **3개 리포의 sqlite 영속 구현**. 인메모리와 동일 시그니처(duck-typed). `PERSISTENCE=db`에서 주입. ※ `ConversationStore`는 영속 대상 아님(인메모리 유지). |

### 조립 / 공통
| 위치 | 핵심 심볼 | 역할 |
|---|---|---|
| `app/container.py` | `Container`(dataclass), `build_container()` | 의존성 와이어링. `PERSISTENCE` 토글로 인메모리↔sqlite 리포만 교체, 나머지 불변. |
| `app/principal.py` | `Principal`, `resolve_principal`, `multitenant_enabled`, `UserDirectory`, `default_principal`/`guest_principal` | 요청 신원 → Principal → User 프로필. `MULTITENANT` off면 기본 사용자 폴백. |
| `app/concurrency.py` | `KeyedLock` | 키별 `threading.Lock`. 같은 키(user_id·order_id) 임계구역 직렬화, 다른 키는 독립. |
| `app/llm.py` | `MODEL`, `get_client`/`get_async_client`, `chat_completion`/`achat_completion`(세마포어+백오프) | LLM 클라이언트·동시성 래퍼(provider-agnostic, ADR-0034). |
| `app/companion.py`·`compaction.py`·`recommendation.py`·`reengagement.py` | `CompanionService`·`CompactionService`/`RuleBasedCompactor`·`RecommendationService`·`ReEngagementService` | 이어가기·컴팩션·추천·선제 재관여. |
| `app/errors.py` | `ConfirmationRequired`·`OutOfStock`·`PickupTransitionError`·`QuoteExpired`·`QuoteForbidden`·`QuoteNotConvertible` | 도메인 예외(API가 409/410/403으로 매핑). |
| `app/tools.py` | `TOOLS`, `call` | LLM tool-loop용 tool 정의(legacy/runtime). |
| `app/fixtures.py` | `USER` 등 데모 데이터. |

---

## 3. 핵심 흐름

### (a) 턴 처리 — `/internal/turn`
```
BFF → WS/POST /internal/turn (text, screen_context, 신원)
  └ _principal(user_id, guest_token)               # 신원 해석(MULTITENANT off면 기본 사용자)
  └ _stream_and_record(...)                         # 종료 후 컴패니언 record_turn(비차단)
      └ _stream_turn(text, screen_context, principal)   # 토글 디스패치
          ⓪ CAPABILITY_ORCH on → _cap_orch.astream(...)        # capability 단일 백본(권장 경로)
          ① LLM_BACKED off     → _orch.stream_turn(...)        # 결정적 섹션(플래너 없음)
          ② LLM_BACKED on,MA off → legacy.astream_turn(...)    # LLM tool-loop prose
          ③ LLM_BACKED on,MA on  → runtime.astream_multiagent(...)  # 슈퍼바이저-워커 prose
```
`CapabilityOrchestrator`(①·⓪)의 내부:
```
route(message)  (또는 aroute = LLM 플래너 비동기)
  ├ self.plan(message)                       # 규칙 분류 → rule_plan → validate_plan (룰 폴백)
  ├ llm_planner 있으면:
  │   ├ _plan_cache 조회 (메시지=순수함수 → 캐시 안전, LLM 홉 생략)
  │   ├ planner.propose/apropose(advisory_catalog, message)   # 조언형만 선택
  │   ├ validate_plan(...)                   # 행동형 자동선택 차단
  │   └ _merge_advisory_actions(advisory, rule)  # LLM 조언형 + 규칙 명시 order 병합, 우선순위 정렬
  └ 실패·빈 결과 → rule plan 폴백
↓
_run_capabilities(plan, ctx, message, session)
  ├ 각 capability.run(ctx, message) 순차 실행 — step별 독립 폴백(한 step 실패 ≠ 턴 붕괴)
  ├ diagnose면 gate_repair_ctas(): danger/보증무상 시 부품 CTA 숨김 + 사유, 상담/방문 CTA 항상
  ├ 빈 섹션이면 handle_clarify로 되묻기(R7 — 빈 턴 금지)
  └ 세션 carry 갱신(required_parts·candidates → 다음 턴 order가 이어받음)
↓ §2.1 봉투 방출:  section* → flow(active_flow) → done(message_id)   # 실패 시 error
```
- 행동형 `order`는 **명시 의도일 때만** plan에 포함(자동선택 차단, ADR-0046). 초안(product_card)+확정 CTA만 산출, 실제 커밋은 (b).
- 우선순위: `device_status(0) < troubleshoot(1) < general(2) < recommend(3) < order(4)`.

### (b) 커밋 — 주문/예약
```
BFF → POST /internal/orders (또는 /internal/bookings)
  └ _guest_commit_gate(헤더 우선·본문 폴백, gap ②)
        MULTITENANT on + 게스트 → 401 LoginRequired (로그인 CTA)
  └ OrderService.checkout / checkout_pickup   (with _ORDER_LOCKS.acquire(user_id))
        confirmed=False → DRAFT 생성 → raise ConfirmationRequired
                        → API가 409 ConfirmationRequired + confirmation 템플릿(금액 분해)
        confirmed=True  → place_order(confirmed=True) → Order 반환
  └ 예약(create_booking)도 동형: 게스트 401 → 미확인 409 ConfirmationRequired → confirmed면 book()
```
- 재고 없음 → `OutOfStock` → 409(대체 매장·배송 전환 제시). 픽업 전이 역전이 → `PickupTransitionError` 409.
- 견적 전환(`convert_quote`)도 같은 게이트(확인 409 / 만료 410 / 권한 403 / 전환불가 409).

---

## 4. 계약 경계 (BFF ↔ BE)

| 항목 | 입력/출력 | 비고 |
|---|---|---|
| 신원(헤더) | `X-User-Id`, `X-Guest-Token` | BFF가 인증 후 중계. 헤더 **우선**. |
| 신원(본문 폴백, gap ②) | `TurnRequest.user_id`/`guest_token`, `OrderRequest`/`BookingRequest`의 `user_id`/`guest_token` | 헤더 없을 때 폴백. `OrderRequest.user_id` 기본값 `"usr_01"`은 **명시 전송(`model_fields_set`)일 때만** 로그인으로 인정. |
| WS payload | `{text, screen_context, user_id, guest_token}` | WS 핸드셰이크/메시지가 신원 운반. |
| 턴 출력 | §2.1 봉투: `section*` → `flow` → `done`(실패 시 `error`) | POST는 NDJSON(한 줄=청크 1개). |
| 게스트 커밋 차단 | **401** `LoginRequired` | MULTITENANT off면 게이트 없음(회귀). |
| 미확인 커밋 | **409** `ConfirmationRequired`(+confirmation 템플릿) | 주문·예약·견적전환 공통. |
| 재고/전이/견적 | 409 `OutOfStock`/`PickupTransitionError`/`QuoteNotConvertible`, 410 `QuoteExpired`, 403 `Forbidden` | |

**SoT 링크(여기서 스펙 재서술 금지):**
- 엔드포인트·봉투·신원 헤더 상세 → `docs/api-contract.md`(§2.1·§2.4)
- 신원·커밋 왕복 결정 근거 → `docs/adr/0050-bff-be-identity-and-commit-contract.md`, `docs/adr/0049-multiuser-session-and-commit-contract.md`
- 템플릿 kind·CTA 규칙 → `docs/response-templates.md`
- **계약 변경 시 3계층 동기화**: `bff/gateway/`·`frontend/src/types/contract.ts`까지 같이 갱신(CLAUDE.md 규칙).

---

## 5. 토글 / 모드 (env — 기본 off = 회귀 불변)

| 토글 | 효과 | 기본 |
|---|---|---|
| `LLM_BACKED` | on이면 자연어 LLM 경로 사용. off면 전부 결정적 섹션. | off |
| `MULTIAGENT` | `LLM_BACKED` 위에서 동작. on=슈퍼바이저-워커(`runtime`), off=단일 tool-loop(`legacy`). | off |
| `CAPABILITY_ORCH` | on이면 결정적/멀티에이전트 대신 `CapabilityOrchestrator.astream`으로 라우팅(LLM_BACKED on이면 LLM 플래너, off면 규칙 폴백). | off |
| `MULTITENANT` | on이면 Principal/게스트 신원 해석 + 게스트 커밋 차단. off면 항상 기본 사용자(`usr_01`). | off |
| `PERSISTENCE` (`memory`\|`db`) | `db`면 3개 리포(engagement·conversation_memory·open_loop)를 sqlite로 교체(`SQLITE_PATH`, 기본 `rubicon.db`). | memory |
| `OPENAI_API_KEY` | 실 LLM 호출(`backend/.env` 자동 로드). CI에 없음 → 수동 검증(6절). | — |

> 토글은 `internal.py`에서 **매 호출 평가**(`_llm_backed`·`_multiagent`·`_capability_orch`)되어 런타임 env·`.env`를 반영한다.

---

## 6. 테스트 / 검증

- 결정적 단위/통합: `cd backend && python -m pytest` — **현재 233 passed**(`backend/tests/`).
- 실 LLM 수동 검증(pytest 아님, `OPENAI_API_KEY` 필요):
  - `backend/verify_llm_planner.py` — 규칙 vs LLM plan 비교(F1·F2 장문 교정).
  - `backend/verify_multiturn_long.py` — 장문 멀티턴 분류·carry 실측.
  - `backend/verify_e2e_timing.py` — §2.1 봉투 패리티 + 구간별/총 타이밍.
- 정본 코퍼스: `specs/capability-orchestrator/test-set.md`(+ `test-findings.md`).
- 게이트 정책(CLAUDE.md): BE 변경 시 `backend` pytest. 계약 변경이면 `bff`/`frontend`도 함께 검증.

---

## 7. 현재 상태 & 후속

**된 것**
- capability **단일 백본**으로 결정적 경로 수렴(`core.py` 제거, 스트랭글러 §12.3).
- LLM 플래너 **단일 라우터**(ADR-0048) + 룰 폴백 + plan 캐시 + 조언형/행동형 병합.
- 멀티테넌트/게스트 신원 해석(`principal.py`) + 게스트 커밋 차단(401).
- sqlite 영속 **3리포**(`PERSISTENCE=db`) — duck-typed 합성.
- `KeyedLock` 동시성(주문 커밋·픽업 전이 직렬화).
- 커밋 게이트(409 ConfirmationRequired)·수리 CTA 게이팅(danger/보증).

**후속(§8~11 등)**
- capability에 **LLM prose agent capability** 추가 → `legacy.py`·`runtime.py`(②③ 경로) 제거.
- order 영속(현재 `ConversationStore`·order는 인메모리).
- 게스트 → 로그인 상태 머지(이어가기).
- analytics 싱크(이벤트 택소노미 배선).

**ADR / spec 링크:** `docs/adr/0043`~`0050`(capability·플래너·신원·커밋), `specs/capability-orchestrator/`, `specs/multi-tenant-state/`.

---

## 8. SoT 링크 / 중복 금지

다음은 **권위 문서**다. 이 가이드에서 재서술하지 말고 링크로 위임한다.

| 주제 | 권위 문서 |
|---|---|
| 데이터 모델·스키마·필드 | `docs/data-model.md` |
| 외부 API·WS 봉투·신원 헤더 | `docs/api-contract.md` |
| 템플릿 kind·CTA 규칙 | `docs/response-templates.md` |
| 오케스트레이터 내부(의도·tool·RAG·스트리밍) | `docs/orchestration.md` |
| 멀티에이전트 구조(슈퍼바이저-워커·리뷰) | `docs/agents.md` |
| 전체 아키텍처·Mock↔실 전략 | `docs/architecture.md` |
| 멀티유저 운영·동시성·캐싱 | `docs/operations.md` |
| LLM 프롬프트 정책·가드레일 | `docs/llm-policy.md` |
| 분석 이벤트 택소노미 | `docs/analytics.md` |
| 결정 근거·기각안 | `docs/adr/`(인덱스 `docs/adr/README.md`) |

> **데이터 모델·공개 인터페이스·전체 아키텍처가 바뀌면** 이 문서가 아니라 위 기반 문서를
> 갱신하고, 여기서는 참조만 한다(CLAUDE.md §문서 계층).

# ADR-0049: 멀티유저·세션 격리 + 커밋(CTA→ActionGate) 계약

- **상태**: 채택(부분 구현 — 경계/계약 확정, 풀 멀티테넌시는 후속)
- **관련**: `docs/operations.md`(동시성·세션 격리), ADR-0046·0048(오케스트레이터), 요구사항 17(커밋 게이트)·18(예약), `specs/capability-orchestrator/tasks.md` §3.3·§12

## 배경
내부 API는 MVP로 **단일 전역 컨테이너**(`_container = build_container()`)와 **인메모리 세션**으로 동작한다(`internal.py`). 멀티유저 운영(`operations.md`)으로 가려면 ① 사용자별 상태 격리 ② 세션 누수/동시성 ③ 커밋(주문·예약) 안전이 필요하다. 본 ADR은 **경계와 계약을 확정**하고, 안전한 증분을 지금 반영한다.

## 결정

### A. 세션·상태 격리
- **턴 블랙보드는 이미 `session_id`로 격리**(CapabilityOrchestrator `_sessions`). 본 ADR에서 **경계(`_SESSION_MAX`) 추가** — 초과 시 가장 오래된 세션 evict로 **메모리 누수 방지**(다중 사용자/세션). `_plan_cache`도 경계(`_PLAN_CACHE_MAX`).
- **도메인 상태(기기·주문·예약 등)는 현재 단일 테넌트**(공유 `_container`). 이는 **MVP 경계**로 명시한다. 실 전환 시 **사용자별 컨테이너 레지스트리**(`user_id → Container`) + 요청 인증 컨텍스트(BFF, §2.4)로 분리한다 — 엔드포인트가 `_container`를 직접 참조하므로 **별도 스펙(`specs/multi-tenant-state/`)이 필요한 큰 작업**. 후속.
- **동시성**: 핸들러는 결정적·짧고(타이밍 §9.2: ~0.2ms), LLM 홉은 async(`apropose`)로 이벤트 루프 비차단. 모듈 전역 오케스트레이터의 lazy 생성은 GIL 하에서 재생성돼도 무해(상태 없음). 사용자별 컨테이너 도입 시 레지스트리 접근만 락/원자화.

### B. 커밋(CTA→ActionGate) 계약
되돌릴 수 없는 커밋은 **자동 실행 금지 → CTA 확정 → 게이트 엔드포인트**(R17). 현재 계약:

| CTA `kind` | action | 목적지 엔드포인트 | 게이트 |
|---|---|---|---|
| `order` | commit | `POST /internal/orders` | R17 `ConfirmationRequired`(409) → `confirmed:true` 재요청 |
| `booking` | commit | `POST /internal/bookings` | **R17 게이트 추가(본 작업 ③)** → `confirmed:true` |
| `handoff` | chat | (상담원 연결) | 커밋 아님 |
| `restock_alert`·`recommend`·`select_device`·`compare`·`explain` | chat | 조언형 재질의 | 커밋 아님 |

- **2단계 커밋 왕복이 양쪽(주문·예약) 모두 닫힘** — CTA가 `slot_id`/`part_ids`를 payload로 운반 → 게이트 409(confirmation 템플릿) → 사용자 확인 → 확정. BFF가 REST로 중계.
- **후속(§3.3)**: CTA 회신을 **대화 스트림 안에서** 오케스트레이터가 받아 confirmation 섹션으로 렌더(인-챗 확정 UX). 현재는 REST 게이트로 충족, 인-챗 렌더는 미구현.

## 본 작업에서 반영한 것(안전 증분)
- `_SESSION_MAX`·`_plan_cache` 경계 — 멀티세션 누수 방지.
- 예약 커밋 게이트(③) — 커밋 계약을 주문과 동형으로 완성.
- 레이턴시 캐시(⑤) — route는 메시지의 순수 함수 → 동일 질의 LLM 홉 생략.

## 후속(별도 스펙 필요 — 큰 작업)
- `specs/multi-tenant-state/` — 사용자별 컨테이너 레지스트리·인증 컨텍스트·영속 저장소 전환(인메모리→DB).
- 인-챗 CTA 확정 렌더(§3.3).

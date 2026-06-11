# 풀 저니 시나리오 (구체 데이터 기반)

> `fixtures/`의 더미데이터로 **실제 end-to-end 흐름**을 구체 값으로 보여준다.
> 추상 시나리오·갭은 `scenarios.md`, 흐름 다이어그램은 `docs/diagrams.md`.
> 사용자: `usr_01`(홍길동, 세탁기·냉장고·공기청정기 연동, 동의 4종).
> 더미는 **카테고리별 일부**(세탁기·냉장고·공기청정기)만 — full journey 검증용.

## J1. 세탁기 5C 오류 → 셀프 해결 → 배수필터 주문 (reactive 메인)

| # | 데이터 | 시스템 동작 | 템플릿/CTA | 요구사항 |
|---|--------|-------------|------------|----------|
| 1 | `dev_washer_01.status=UNHEALTHY` | 홈 선제 알림 노출 | `home_summary` → `device_status` | R2·R9-2 |
| 2 | 사용자 "세탁기에서 물이 안 빠져요" | `/chat` → 의도=TROUBLESHOOT | — | R1 |
| 3 | `ano_washer_5c`(error_code) | 기기 상태·이상 식별 | `device_status` | R2 |
| 4 | `sol_washer_5c` (RAG, 오류코드 키 매칭) | 단계 가이드 + 출처 | `guide_steps`(+`Source`) | R3·R16 |
| 5 | `required_parts=[part_drain_filter]` | 부품 매칭(R4) | `product_card`(배수필터 12,000원, in_stock) | R4 |
| 6 | 사용자 [주문] | 확인 게이트 | `confirmation`(R17) | R17 |
| 7 | confirmed | 주문 확정(Mock) | `order_summary`(subtotal·배송비·총액) | R4·R21 |
| 8 | — | 진행 추적 | `status_tracker` | R12 |

## J2. 냉장고 정수필터 선제 알림 → 재주문 (proactive)

| # | 데이터 | 시스템 동작 | 템플릿/CTA | 요구사항 |
|---|--------|-------------|------------|----------|
| 1 | `water_filter.life=0.15 < threshold 0.20` | 임계치 감지 → 알림 생성 | — | R5·6.3 |
| 2 | `usr_01.notify_opt_in=true`·동의 | 빈도·동의 게이트 통과 → 전달 | (인앱) `home_summary` 알림 | R20·R26 |
| 3 | 사용자 알림 탭 | 카드 탭 → **간단 → 브릿지(S4)** | `bridge`(요약+`device_status`, [재주문]) | R9·bridge |
| 4 | `sol_fridge_filter.coverage=free` | 유·무상 표시(무상) | 브릿지 badge | R22 |
| 5 | 사용자 [재주문] | `part_water_filter`(38,000원) 주문 | `confirmation`→`order_summary` | R4·R17 |
| 6 | `EngagementRecord(viewed/acknowledged)` | 확인 기록 → 중복 알림 억제 | — | R29 |

## J3. 공기청정기 HEPA 품절 → 입고 알림/대체 + 신제품 추천 (엣지)

| # | 데이터 | 시스템 동작 | 템플릿/CTA | 요구사항 |
|---|--------|-------------|------------|----------|
| 1 | `hepa_filter.life=0.12 < 0.15` | 교체 시기 선제안 | `device_status` | R5 |
| 2 | `part_hepa.in_stock=false` | **품절** → 주문 CTA 비활성 | `product_card`(품절 표기) | R4·R13 |
| 3 | — | 대안: 입고 알림 신청 / 대체 안내 | 안내(text) | R13 |
| 4 | `usr_01.interest_categories=[air_purifier]` | 개인화 추천(관심 반영) | `recommendation_list`(`prod_purifier_cube`, 근거) | R8 |
| 5 | `EngagementRecord` | 이미 본 추천 재노출 억제 | — | R29 |

## J4. 세탁기 5C 셀프 실패 → 방문 예약 (핸드오프)

| # | 데이터 | 시스템 동작 | 템플릿/CTA | 요구사항 |
|---|--------|-------------|------------|----------|
| 1 | J1 4단계 이후 "해도 안 돼요" | 미해결 인지 | — | R25 |
| 2 | `sol_washer_5c.escalation_needed`/위험 판단 | 트리아지 → 출장 수리 권고 | `handoff_card` | R18·트리아지(design §8.3) |
| 3 | 사용자 [방문 예약] | `HandoffPort.list_slots(visit_type=REPAIR)` | `booking`(슬롯) | R18 |
| 4 | 슬롯 선택 [예약 확정] | `book_slot` (Mock) | `status_tracker`(예약 진행) | R18·R12 |
| 5 | 방문 맥락 전달 | 대화 맥락(기기·시도한 해결) 동봉 | — | R18-2 |

## J5. 복합 질문 (다중 의도) → 분해·우선순위·부분 처리 (R7)

> 입력: **"세탁기 물 안 빠지는 거 해결법 알려주고, 냉장고 정수필터랑 공기청정기 HEPA 필터도 주문해줘."**
> 의도 3개: TROUBLESHOOT(세탁기) · ORDER(정수필터) · ORDER(HEPA).

| # | 데이터/의도 | 시스템 동작 | 템플릿/CTA | 요구사항 |
|---|------------|-------------|------------|----------|
| 1 | 입력(복합) | 의도 분해 `[TROUBLESHOOT, ORDER, ORDER]` | (IntentResult) | R7·6.1 |
| 2 | 우선순위(안전·CS 먼저) | 정렬: 세탁기 해결 → 주문들 | — | 6.6 |
| 3 | `ano_washer_5c`·`sol_washer_5c` | **섹션1**: 해결 가이드 | `guide_steps` | R3 |
| 4 | `part_water_filter`(in_stock) | **섹션2**: 주문 카드 | `product_card`→`confirmation` | R4·R17 |
| 5 | `part_hepa`(**in_stock=false**) | **섹션3**: 주문 불가 → 입고 알림/대체 안내 | `text`(불가 사유) | R4·R13 |
| 6 | 종합 | `handled=[세탁기, 정수필터]`, `unhandled=[HEPA(품절)]` 구분 | 섹션 묶음 응답 | **R7-3** |

- **핵심** — 복합 질문은 **의도별 섹션으로 묶어** 응답하고, 처리/미처리를 명확히 구분(R7-2·R7-3).
  부분 실패(HEPA 품절)는 전체를 막지 않고 해당 의도만 폴백(R13).
- 흐름 다이어그램: `docs/diagrams.md` → 복합 질문 분해(R7).

---

## 커버리지 요약
- **데이터 3종** — SmartThings(devices·anomalies)·CS(solutions)·제품(catalog) 더미가 모두 한 저니에서 맞물림.
- **요구사항** — R1~R29 핵심 경로(이상감지·해결·주문·선제·브릿지·핸드오프·개인화·확인정보·취소/금액·**복합질문 R7**)를 5개 저니로 커버.
- **fixtures → Mock 어댑터/Stub** — 위 더미는 `Mock*` 어댑터(`data-model.md` §8)·계약 Stub(`api-contract.md` §5)이 그대로 반환·재생한다.

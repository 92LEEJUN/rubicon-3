# 작업 (Tasks) — O2O 풀(매장 픽업·재고·견적 이어보기)

> `design.md` 를 실제 구현으로 나눈 체크리스트. 각 항목은 작고 검증 가능한 단위로 쪼개고,
> 끝에 관련 요구사항 번호(O1~O8)를 표기한다. 완료한 항목은 `[x]` 로 체크한다.
> 공유 타입·계약은 새로 정의하지 않고 `docs/`(data-model·api-contract)를 참조/갱신한다.

## 0. 사전 정렬 (기반 문서 확인)

- [ ] 0.1 `StorePort`·`QuotePort`·`Order`(픽업 필드)·`Store`·`Quote` 타입이 `docs/data-model.md`에
  선반영돼 있음을 확인하고, 부족 필드가 있으면 **data-model.md를 갱신**한다 _(O3·O5·O8)_
- [ ] 0.2 §3.4 결정적 엔드포인트 계약(stores·stock·pickup·quotes·convert)을 `docs/api-contract.md`
  §2.2에 추가 반영한다(확정 후) _(O8-4)_

## 1. StoreService — 거점·재고 _(O1·O2)_

- [ ] 1.1 `StoreService.find_stores(geo, type)` 구현 — `StorePort.find_stores` 호출·유형 필터 _(O1-1·O1-2)_
- [ ] 1.2 위치 없음/거부 시 위치 입력 요청 또는 배송 폴백 분기 _(O1-3·O8-1)_
- [ ] 1.3 거점 표시 데이터(이름·유형·주소·운영시간) 매핑 _(O1-4)_
- [ ] 1.4 `StoreService.check_stock(store_id, part_id)` 구현 — `StorePort.check_stock` 게이트 _(O2-1)_
- [ ] 1.5 재고 없음 → 픽업 진행 비활성 + 대체 매장/배송 제안 _(O2-2·O2-3)_

## 2. OrderService 확장 — 픽업(BOPIS) 라이프사이클 _(O3·O4)_

- [ ] 2. 픽업 주문 생성·상태 전이 _(O3·O4)_
  - [ ] 2.1 픽업 주문 생성 — `Fulfillment.PICKUP`·`store_id`·`pickup_status=RESERVED`, 생성 전 재고
    게이트(1.4) _(O3-1)_
  - [ ] 2.2 픽업 확정 직전 `ActionGatePort.requires_confirmation` 확인 게이트 _(O3-2·R17)_
  - [ ] 2.3 픽업 상태머신 구현 — `RESERVED→READY→PICKED_UP|EXPIRED` 허용·역전이 거부 _(O3-6)_
  - [ ] 2.4 `READY` 전이 시 `AlertPort.deliver` 준비완료 선제 알림 _(O3-3·R20)_
  - [ ] 2.5 `PICKED_UP` 전이(매장 수령·본인 확인) _(O3-4)_
  - [ ] 2.6 픽업 상태·픽업 매장 조회/표시(`status_tracker`/`order` bridge) _(O3-5·R12)_
  - [ ] 2.7 미수령 만료 → `EXPIRED` 전이 + 취소/환불(R21) 연계 _(O4-1·O4-2)_
  - [ ] 2.8 재고 소진 시 대체 매장/배송 전환 제안 _(O4-3·O8-1)_

## 3. StoreService — 견적 이어보기 _(O5)_

- [ ] 3.1 `StoreService.get_quote(ref)` 구현 — `QuotePort.get_quote` 호출 _(O5-1)_
- [ ] 3.2 본인 확인(`Quote.user_id` 불일치 거부) _(O5-2)_
- [ ] 3.3 만료(`expires_at`) 검증 → 재견적 안내 _(O5-3)_
- [ ] 3.4 현재가/재고 변동 검증 → 재확인·대체 제안 _(O5-4)_
- [ ] 3.5 견적 표시(`order_summary`/`bridge`) 매핑 _(O5-1)_

## 4. OrderService 확장 — 견적 → 주문 전환 _(O6)_

- [ ] 4.1 `ACTIVE` 견적만 전환 가능 가드 _(O6-2)_
- [ ] 4.2 전환 시 현재가·재고 재검증 + 차이 고지 _(O6-3)_
- [ ] 4.3 확인(R17) 후 `Order` 생성 + `Quote.status=CONVERTED` 전이 _(O6-1·R17)_
- [ ] 4.4 전환 주문 이행 방식 선택(배송/픽업 → 2장 재사용) _(O6-4)_

## 5. 트리아지 · 센터 예약 핸드오프 _(O7)_

- [ ] 5.1 트리아지 결정 로직 — 진단(R2·R3) + 보증(R22) + safety/pro_required → self/기사/센터 _(O7-1·O7-3)_
- [ ] 5.2 위험·셀프 부적절 → 기사/센터 우선 안내 _(O7-2·R23)_
- [ ] 5.3 센터 거점 선택(`StoreType.SERVICE_CENTER`) + 슬롯 조회·예약(`HandoffPort.book_slot`,
  `visit_type`·`store_id`) _(O7-4·R18)_
- [ ] 5.4 핸드오프 맥락 전달(`context_ref=Conversation.id`) _(O7-5·R18)_
- [ ] 5.5 불확실 → 상담원(`ServiceRequestType.AGENT`) 연결 _(O7-6·R16-2)_

## 6. 결정적 엔드포인트 (api-contract 스타일) _(O8-4)_

- [ ] 6.1 `GET /stores`·`GET /stores/{id}/stock/{part_id}` _(O1·O2)_
- [ ] 6.2 픽업 `POST /cart`·`POST /orders`(확인·`409`)·`GET /orders/{id}` _(O3·R17·R12)_
- [ ] 6.3 `POST /orders/{id}/pickup`(전이, 역전이 `409`) _(O3·O4)_
- [ ] 6.4 `GET /quotes/{ref}`(본인 `403`·만료 `410`)·`POST /quotes/{ref}/convert`(`409`) _(O5·O6·R17)_
- [ ] 6.5 `GET /bookings/slots`(`visit_type=center`)·`POST /bookings`(센터) _(O7·R18)_

## 7. Mock 어댑터 · 폴백 _(O8)_

- [ ] 7.1 `MockStorePort` — 고정 거점·재고 fixture(불변식 만족, 재고 있음/없음 케이스) _(O8-2)_
- [ ] 7.2 `MockQuotePort` — 고정 견적 fixture(active·expired·타인·현재가 변동 케이스) _(O8-2)_
- [ ] 7.3 픽업/견적 커밋 확인 UX 실제 + 처리 Mock(성공/실패·취소/환불) _(O8-3·ADR-0033)_
- [ ] 7.4 §5 폴백 표 각 분기 구현(StorePort/QuotePort 실패·위치 없음·재고 없음·만료 등) _(O8-1·R13)_

## 8. 테스트 _(O1~O8)_

- [ ] 8.1 단위 — 픽업 상태 전이/역전이 거부, 견적 본인·만료·현재가 검증, 트리아지 분기 _(O3·O5·O7)_
- [ ] 8.2 계약 — `StorePort`/`QuotePort` Mock/실 동일 계약, 빈 결과·실패 폴백 _(O8-2)_
- [ ] 8.3 통합 — BOPIS e2e, 재고 없음→대체/배송, 견적→전환, 트리아지→센터 예약 _(O1~O7)_
- [ ] 8.4 확인 게이트 — 픽업/전환/취소 미확인 `409`, 확인 후 처리 Mock _(O8-3·R17)_

## 진행 메모
<!-- 구현 중 설계와 달라진 점·결정을 기록한다. 공유 타입·계약 변경 시 docs/data-model.md·
     docs/api-contract.md 와 본 design.md 를 함께 갱신한다(CLAUDE.md 규칙). -->
- 새 엔티티/Enum/Port를 만들지 않는다. 부족하면 `docs/data-model.md`를 갱신하고 여기서 참조한다.

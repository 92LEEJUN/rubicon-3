# O2O 시나리오 맵 (양방향)

> 시나리오 모음의 일부. 인덱스: [`README.md`](./README.md).

O2O는 단방향(온라인→오프라인)이 아니라 **reverse(오프라인→온라인)** 가 차별점. 거의 모든 시나리오가
**거점(`Store`/서비스센터) + 슬롯(`Booking`)** 위에 서고, **`Quote`(견적)** 가 오프라인↔온라인을 잇는다.
대부분 **파트너 시스템 연동**이라 MVP는 Mock/비범위.

## A. Online → Offline
| 시나리오 | MVP | 모델 |
|----------|-----|------|
| 가까운 판매처 방문 안내 | 후속 | `StorePort.find_stores`·`Store` |
| 매장 재고 확인 + 픽업(BOPIS) | 후속 | `Order.fulfillment=PICKUP`·`StorePort.check_stock` |
| 체험/데모·오프라인 상담 예약 | 후속 | `BookingSlot`·`Store(EXPERIENCE)` |
| 방문 **설치** 예약 | 후속 | `Booking(visit_type=INSTALL)` |
| 서비스센터 방문 예약 | **MVP(핸드오프 Mock)** | `Booking(SERVICE_CENTER)`·`HandoffPort` |
| 수리기사 방문 요청 | **MVP(핸드오프 Mock)** | `Booking(visit_type=REPAIR)`·R18 |
| 반품/교환 매장 방문·수거 | 후속 | (R21 연계) |

## B. Offline → Online (reverse)
| 시나리오 | MVP | 모델 |
|----------|-----|------|
| 매장 견적/상담 내역 온라인 이어보기 | 후속 | `QuotePort.get_quote`·`Quote(OFFLINE)` |
| 매장 직원 장바구니/견적 앱 전송 | 후속 | `Quote`→`Order` 전환 |
| 오프라인 구매 제품 온라인 등록·연동 | 후속 | 제품 등록 + SmartThings 연동(R15) |
| 오프라인 영수증/주문 이력 통합 | 후속 | `Order` import·보증(R22) 연계 |

## C. 서비스 O2O (A/S)
| 시나리오 | MVP | 모델 |
|----------|-----|------|
| 방문/센터 트리아지(self/기사/센터) | **MVP 일부** | 해결 가이드(R3)·핸드오프(R18) |
| 방문 전 사전 진단·접수 | 부분 | 대화 맥락 전달(R18-2) |
| 수리 견적 사전 확인(유/무상) | **MVP** | `WarrantyPort`(R22) |
| 부품 사전 준비/기사 지참 | 후속 | `Solution.required_parts`·O2O |
| A/S 진행 추적 + 기사 도착 알림 | 부분 | `status_tracker`(R12)·선제알림(R20) |

> **MVP 슬라이스** = 서비스센터/수리 방문 핸드오프(R18, Mock) + 수리 견적 유/무상(R22) + 온라인 주문(R4).
> 나머지(픽업·견적 이어보기·오프라인 통합)는 **후속 O2O 확장**으로 인터페이스(`StorePort`·`QuotePort`)만 미리 둔다.
> 차별 흐름 3종(견적 이어보기·픽업·트리아지)의 **상세 흐름·엣지**는 `../design.md` §8, **시퀀스**는 `docs/diagrams.md` §O2O.

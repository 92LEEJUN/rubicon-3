# 통합 쇼핑·서비스·IoT 앱 아키텍처 설계

> 삼성닷컴(커머스) + 삼성전자서비스(A/S) + 스마트띵스(IoT) 의 기능을 하나의 앱으로 통합하고,
> 그 위에 **어디서나 호출 가능한 AI 어시스턴트**와 **O2O(매장 연계)** 경험을 얹는 시스템의 아키텍처 설계 문서.

---

## 1. 목표와 핵심 시나리오

### 1.1 제품 목표
- 3개의 이질적인 도메인(커머스 / A/S / IoT)을 **하나의 일관된 사용자 경험**으로 통합한다.
- **AI 어시스턴트**를 모든 화면에서 오버레이로 호출할 수 있고, 단순 응답을 넘어 **실제 액션(구매·수리 접수·예약)** 까지 수행한다.
- 보유 기기를 SmartThings와 연결해 **고장 상황을 자동 인지**하고, 필요 시 **제품 구매 또는 수리기사 요청**으로 자연스럽게 이어준다.
- **O2O**: 보고 있는 제품에 대해 실제 매장 방문 예약이 가능하고, 방문 후 **상담 내용을 앱에서 다시 확인**할 수 있다.

### 1.2 대표 시나리오 (이 시스템의 존재 이유)
1. **고장 → 액션**: 세탁기에서 비정상 텔레메트리 발생 → 시스템이 고장 가능성 인지 → 사용자에게 알림 → 어시스턴트가 "수리 접수" 또는 "신제품 구매" 중 선택지를 제시하고 그 자리에서 처리.
2. **화면 컨텍스트 기반 어시스턴트**: 사용자가 특정 냉장고 상세 페이지를 보는 중 어시스턴트 호출 → "이 제품 우리집에 설치 가능?" → 어시스턴트가 현재 보는 상품 + 보유 기기 + 주거 정보로 답변.
3. **O2O 왕복**: 상품 상세에서 "매장에서 직접 보기" → 매장 예약 → 방문/상담 → 상담 기록이 앱에 동기화되어 이후 재열람.

### 1.3 설계 우선순위
가장 어려운 부분은 단일 기능 구현이 아니라 **3개 도메인을 가로지르는 오케스트레이션**이다.
- 어시스턴트와 IoT(고장 감지) 도메인이 다른 모든 도메인을 호출하는 **횡단 오케스트레이터** 역할을 한다.
- "고장 감지 → 구매 또는 수리"가 핵심 결합 지점이며, 아키텍처는 이 흐름을 1급 시민으로 다룬다.

---

## 2. 확정 기술 스택

| 레이어 | 기술 | 비고 |
|--------|------|------|
| **FE (웹)** | Next.js (React, TypeScript) | App Router 기반 SSR/RSC |
| **FE (모바일)** | React Native (TypeScript) | 웹과 도메인 로직/타입 공유 (monorepo) |
| **BFF** | NestJS (Node.js, TypeScript) | 화면 단위 aggregation + 스트리밍 중계 |
| **BE** | FastAPI (Python) | 도메인별 마이크로서비스 |
| **LLM** | Azure OpenAI (GPT, gpt-5.4 계열) | tool-calling 기반 오케스트레이션 |
| **인프라** | AKS (Azure Kubernetes Service) | |
| **메시징** | Azure Service Bus / Event Hubs | 이벤트 기반 고장 감지 파이프라인 |
| **데이터** | 도메인별 분리 (예: Azure DB for PostgreSQL, Cosmos DB) | DB-per-service |
| **검색/벡터** | Azure AI Search | 카탈로그 검색 + 어시스턴트 RAG |
| **캐시** | Azure Cache for Redis | 세션/조합 결과/레이트리밋 |

> FE 모바일은 React Native를 선택해 웹(Next.js)과 **TypeScript 도메인 로직·타입·API 클라이언트를 monorepo에서 공유**한다. (Flutter 대안 대비 코드/인력 재사용에서 유리)

---

## 3. 도메인 분해 (Bounded Context)

하나의 거대 서비스가 아니라 **도메인별 마이크로서비스**로 분리한다. 각 서비스는 자기 데이터를 소유한다(DB-per-service).

| 도메인 (서비스) | 책임 | 원본 대응 |
|------------------|------|-----------|
| **Catalog / Commerce** | 상품·가격·재고·장바구니·주문·결제 | 삼성닷컴 |
| **Service / Repair** | A/S 접수, 증상 진단, 수리기사 배정, 보증 관리 | 삼성전자서비스 |
| **Device / IoT** | 보유기기 레지스트리, 텔레메트리 수집, 고장 이벤트 발행 | 스마트띵스 |
| **O2O / Retail** | 매장 검색·예약·방문 체크인·상담 기록 | O2O |
| **Assistant** | LLM 오케스트레이션, 컨텍스트 수집, tool 실행 | 신규 (횡단) |
| **Identity / Account** | 삼성계정 SSO, 인증/인가, 동의(consent) 관리 | 공통 |
| **Notification** | 푸시/알림(고장·예약·주문 상태) | 공통 |

핵심: **Assistant 와 Device 도메인은 다른 모든 도메인의 API를 호출하는 횡단 오케스트레이터**다.

---

## 4. 레이어 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│ FE  (Next.js 웹 / React Native 모바일)                           │
│  - 화면/상태 관리                                                 │
│  - 어시스턴트 위젯: 전역 오버레이, "현재 화면 컨텍스트"를 동봉    │
│  - 스트리밍 응답 렌더링 (SSE/WebSocket 구독)                       │
└───────────────────────────────┬─────────────────────────────────┘
                                 │  화면용 단일 API (GraphQL or REST)
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ BFF  (NestJS)                                                     │
│  - 여러 BE 도메인 호출을 1개 화면용 응답으로 조합(aggregation)    │
│  - 세션 / 화면별 권한 / 응답 캐싱                                 │
│  - 어시스턴트 토큰 스트리밍 중계 (얇은 passthrough)               │
│  - 웹/모바일 각각의 화면 모델(view model)에 최적화               │
└───────────────────────────────┬─────────────────────────────────┘
                                 │  내부 통신 (REST/gRPC + mTLS)
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ BE  (FastAPI 마이크로서비스 + 외부연동 + LLM 오케스트레이션)      │
│                                                                   │
│  [Catalog] [Service] [Device] [O2O] [Identity] [Notification]    │
│                                                                   │
│  [Assistant Orchestrator] ── Azure OpenAI (tool-calling) ──┐      │
│        └─▶ [Tool Gateway] ──(인가·검증·확인·감사)──▶ 도메인 API   │
│                                                                   │
│  [External Adapter Layer / Anti-Corruption Layer]                │
│     ├─ SmartThings Cloud  ├─ 결제 PG  ├─ 물류  ├─ 매장 시스템     │
└──────────────┬────────────────────────────────────────┬─────────┘
               │  이벤트 발행/구독                        │  외부 호출
               ▼                                          ▼
   Azure Service Bus / Event Hubs            외부 시스템 (PG, 물류, ST Cloud)
```

### 4.1 레이어별 책임 경계 원칙
- **FE**: 표현·상호작용만. 비즈니스 규칙·도메인 조합 로직을 두지 않는다.
- **BFF**: **화면 중심(Backend For Frontend)**. 도메인을 "화면이 필요로 하는 모양"으로 조합·변환. 단, 비즈니스 트랜잭션이나 부수효과는 만들지 않는다.
- **BE**: 도메인 규칙·트랜잭션·외부연동·LLM 오케스트레이션의 **단일 진실 공급원**.

### 4.2 왜 LLM 오케스트레이션을 BFF가 아닌 BE에 두는가
어시스턴트는 **결제·수리 접수 같은 실제 부수효과를 tool로 실행**한다. 따라서 트랜잭션·권한·감사 로그·idempotency가 있는 **BE**에 둬야 한다. BFF는 **스트리밍 토큰을 FE로 흘려보내는 얇은 중계**만 담당한다.

---

## 5. FE 설계

### 5.1 Monorepo 구성
```
apps/
  web/         # Next.js
  mobile/      # React Native
packages/
  api-client/  # BFF API 클라이언트 (타입 공유)
  domain/      # 공유 도메인 타입/유틸 (DTO, enum)
  ui-core/     # 플랫폼 비종속 로직 (어시스턴트 상태머신 등)
```

### 5.2 어디서나 호출 가능한 어시스턴트 위젯
- **전역 컴포넌트**로 루트 레이아웃에 마운트(웹: App Router root layout / 모바일: 루트 네비게이터 오버레이).
- 호출 시 **현재 화면 컨텍스트**를 함께 전송:
  - 현재 라우트/화면 종류 (예: `product_detail`)
  - 화면의 핵심 엔티티 ID (예: 보고 있는 상품 `sku`, 보유 기기 `deviceId`)
  - 선택 영역/스크롤 위치 등 보조 컨텍스트(선택)
- 응답은 **스트리밍 구독**(SSE 우선, 양방향 필요 시 WebSocket)으로 렌더링.
- 어시스턴트가 제안하는 액션(구매/수리/예약)은 **확인 카드(confirmation card)** 로 노출 → 사용자가 명시적으로 승인해야 실행.

### 5.3 컨텍스트 페이로드 예시
```jsonc
{
  "screen": "product_detail",
  "entities": { "sku": "RF85C90...", "category": "refrigerator" },
  "ownedDeviceRef": "dev_8f21...",   // 관련 보유기기가 있으면
  "locale": "ko-KR"
}
```

---

## 6. BFF 설계 (NestJS)

### 6.1 책임
- **Aggregation**: 한 화면이 필요로 하는 여러 도메인 데이터를 병렬 호출 후 조합.
  - 예: 홈 화면 = 추천상품(Catalog) + 보유기기 상태(Device) + 진행 중 A/S(Service) + 예정 매장방문(O2O).
- **View Model 변환**: 웹/모바일 각 화면에 맞는 응답 형태로 가공.
- **세션·인증 컨텍스트 전파**: Identity에서 검증된 토큰을 BE 호출 시 전파.
- **어시스턴트 스트리밍 중계**: FE ↔ BE Assistant 서비스 사이의 SSE/WebSocket passthrough. 토큰을 버퍼링 없이 흘려보낸다.

### 6.2 API 스타일
- 클라이언트 ↔ BFF: **GraphQL**(화면별 데이터 요구가 다양/중첩이면 유리) 또는 **REST aggregation 엔드포인트**(단순/캐싱 친화적).
  - 권장: 초기엔 화면별 REST aggregation, 화면 다양성이 커지면 GraphQL 도입 검토.
- BFF ↔ BE: 내부 **REST 또는 gRPC**, mTLS.

### 6.3 BFF가 하지 말아야 할 것
- 도메인 비즈니스 규칙(가격 계산, 보증 판정 등) — BE에 둔다.
- 부수효과를 일으키는 오케스트레이션(결제, 수리 접수) — BE Assistant/도메인 서비스에 둔다.

---

## 7. BE 설계 (FastAPI) — 핵심 고민 2가지

### 7.1 외부 API 연동 — Anti-Corruption Layer + Adapter

외부 시스템(SmartThings Cloud, 결제 PG, 물류, 매장 시스템)을 **Adapter로 격리**하여 외부 스키마가 도메인 모델을 오염시키지 않게 한다.

```
도메인 서비스  ──(도메인 모델/포트 인터페이스)──▶  Adapter(ACL)  ──▶  외부 API
                                                   └ 외부 DTO ↔ 도메인 모델 변환
```

**회복성(resilience) 필수 요소**:
- **타임아웃 + 서킷 브레이커**: 외부 장애가 전체로 전파되지 않도록.
- **재시도 + 지수 백오프**: 일시적 오류 대응. 단, **비멱등 연산엔 신중**.
- **Idempotency Key**: 결제·수리 접수·주문 등 **되돌리기 어려운 외부 호출**에 필수. 중복 실행 방지.
- **Bulkhead**: 외부 의존성별 리소스/커넥션 풀 격리.
- **Outbox 패턴**: 외부 호출과 로컬 상태 변경의 정합성 보장(특히 이벤트 발행).

**SmartThings 텔레메트리는 동기 호출이 아니다**:
- 폴링이 아니라 **웹훅/이벤트 구독 → Event Hubs → 고장 감지 컨슈머** 로 받는다(§8 참조).

### 7.2 LLM 연동 — 전용 Assistant 서비스 + Tool Gateway

BE의 LLM 연동은 **두 개의 독립 컴포넌트**로 분리한다.
**(A) Assistant Orchestrator** — LLM과의 대화/추론 루프 담당.
**(B) Tool Gateway** — LLM이 호출하는 모든 tool의 **단일 관문**으로, 권한·검증·확인·감사를 한곳에 모은다.

```
            ┌──────────────────────────────────────────────┐
 사용자 발화 │ (A) Assistant Orchestrator (FastAPI)          │
 + 화면컨텍 ─▶│   1. 컨텍스트 수집 (화면/보유기기/최근주문)    │
            │   2. 의도 분류/라우팅 (경량 모델)             │
            │   3. Azure OpenAI 호출 (tool-calling)         │◀──▶ Azure OpenAI (GPT)
            │   4. tool 호출은 Tool Gateway에만 위임         │
            │   5. 응답 스트리밍 (SSE)                       │
            └───────────────┬──────────────────────────────┘
                            │ tool 실행 요청 (tool명 + 인자)
                            ▼
            ┌──────────────────────────────────────────────┐
            │ (B) Tool Gateway                              │
            │   - Tool Registry: 스키마/권한/부수효과 메타  │
            │   - 인자 검증 (JSON Schema)                   │
            │   - 인가: 사용자 권한 범위 확인               │
            │   - 부수효과 tool ⇒ proposal 생성 (즉시 실행X)│
            │   - 멱등성/레이트리밋/감사 로깅               │
            │   - 도메인 API로 라우팅 (ACL 경유)            │
            └───────────────┬──────────────────────────────┘
                            │ 검증·인가된 호출만 전달
                            ▼
            [Catalog] [Service] [Device] [O2O] ... 기존 도메인 API
```

#### (A) Assistant Orchestrator의 책임
- 대화 세션/컨텍스트 관리, 모델 라우팅, tool-calling 루프 구동, 응답 스트리밍.
- **도메인 시스템을 직접 호출하지 않는다.** tool 실행은 반드시 Tool Gateway에 위임 → LLM 추론 로직과 시스템 액션 권한을 분리.

#### (B) Tool Gateway의 책임 (핵심)
LLM이 신뢰 경계 안으로 들어오는 지점이므로, **모든 tool 호출이 반드시 통과하는 단일 관문**으로 둔다.
- **Tool Registry**: 각 tool의 JSON Schema, 대상 도메인 API, 권한 요구사항, **부수효과 여부(읽기/쓰기)**, 확인 필요 여부를 선언적으로 관리. Azure OpenAI에 노출하는 function 정의도 여기서 단일 소스로 생성.
- **인자 검증**: LLM이 생성한 인자를 스키마로 엄격 검증(환각 방지). 검증 실패는 도메인에 닿기 전 차단.
- **인가(Authorization)**: 호출 사용자 권한 범위 내에서만 실행. 사용자 소유가 아닌 기기/주문/상담 접근 차단.
- **부수효과 가드 (Human-in-the-loop)**: `createRepairRequest`·`placeOrder`·`bookStoreVisit` 등 쓰기 tool은 **즉시 실행하지 않고 proposal 토큰을 생성**해 FE 확인 카드로 반환. 사용자가 승인하면 그 proposal을 다시 Gateway가 **검증 후 실제 실행**.
- **멱등성/레이트리밋**: proposal 단위 idempotency key, 사용자/세션별 호출 레이트리밋.
- **감사/관측성**: 모든 tool 호출(입력 인자·결과·인가 판정)에 trace ID로 감사 로그 기록(개인정보 마스킹).
- **ACL 경유 호출**: 실제 도메인/외부 호출은 §7.1의 Adapter(ACL)를 통해 수행.

#### 그 외 원칙
- LLM은 **DB를 직접 만지지 않는다.** 도메인의 **기존 API를 tool로만 호출**한다 → 권한·검증 로직 재사용.
- **2-tier 라우팅**: 가벼운 의도분류·요약은 경량 배포(낮은 비용/지연), 복잡한 다단계 추론은 상위 모델로. Azure OpenAI deployment를 용도별로 분리.
- **컨텍스트 주입(RAG/구조화)**: "지금 보는 화면 + 보유 기기 + 최근 주문/상담"을 구조화 컨텍스트로 주입. 카탈로그/매뉴얼/상담기록은 **Azure AI Search** 로 검색해 근거 제공.
- **비용/지연 최적화**: 프롬프트 캐싱, 스트리밍 우선, 컨텍스트 토큰 예산 관리.
- **가드레일**: 프롬프트 인젝션 방어(외부 텍스트는 신뢰 데이터로 취급하지 않음), 출력 정책 필터. 권한 경계의 실질적 강제는 Tool Gateway가 담당.

#### Tool 카탈로그 (예시)
| Tool | 도메인 | 부수효과 | 확인 필요 |
|------|--------|----------|-----------|
| `searchProducts` | Catalog | 없음(읽기) | 아니오 |
| `getOwnedDevices` | Device | 없음(읽기) | 아니오 |
| `diagnoseSymptom` | Service | 없음(읽기) | 아니오 |
| `createRepairRequest` | Service | **있음** | **예** |
| `addToCart/ placeOrder` | Commerce | **있음** | **예** |
| `bookStoreVisit` | O2O | **있음** | **예** |
| `getConsultationHistory` | O2O | 없음(읽기) | 아니오 |

---

## 8. 이벤트 기반 고장 감지 → 액션 플로우 (핵심 흐름)

```
[SmartThings Cloud]
      │ 디바이스 이벤트/텔레메트리 (웹훅 구독)
      ▼
[Device Service] ──발행──▶ [Event Hubs: device.telemetry]
                                     │
                                     ▼
                        [Fault Detection Consumer]
                          - 규칙/이상탐지로 고장 가능성 판정
                          - 필요 시 LLM으로 증상 해석(보조)
                                     │ 고장 확정
                                     ▼
                        [Event: device.fault.detected]
                          ├──▶ [Notification] 사용자 푸시 알림
                          └──▶ [Assistant] 액션 제안 생성
                                     │
                       사용자가 알림/어시스턴트에서 선택
                          ├─ "수리 요청" ─▶ Service.createRepairRequest (확인 후)
                          └─ "신제품 구매" ─▶ Commerce.placeOrder (확인 후)
```

**설계 포인트**:
- 텔레메트리는 **고볼륨/비동기** → Event Hubs로 흡수, 백프레셔 관리.
- 고장 판정은 **규칙 기반 1차 + (선택)LLM 보조 해석**. LLM은 판정 자동화의 주체가 아니라 **설명/우선순위화** 보조.
- 고장 이벤트는 알림과 어시스턴트로 **fan-out**. 실제 구매/수리는 항상 **사용자 확인 후** 실행.

---

## 9. O2O 플로우 (매장 방문 ↔ 상담 기록)

```
상품 상세 ──"매장에서 보기"──▶ [O2O] 매장 검색(재고/거리) ──▶ 예약(bookStoreVisit)
                                                                  │
                                              방문/체크인 ◀── 푸시 알림(Notification)
                                                                  │
                            매장 단말/상담사 시스템 ──상담기록──▶ [O2O] 상담 기록 저장
                                                                  │
                                          앱에서 "상담 내역" 재열람 (getConsultationHistory)
```

- 매장 시스템 연동은 **Adapter(ACL)** 로 격리.
- 상담 기록은 O2O 서비스가 소유하고, 어시스턴트가 `getConsultationHistory` tool로 참조해 후속 대화에 활용.

---

## 10. 횡단 관심사 (Cross-cutting)

### 10.1 인증/인가
- **Identity 서비스**가 삼성계정 SSO(OIDC) 기준 토큰 발급/검증.
- BFF가 토큰 검증 후 사용자 컨텍스트를 BE로 전파. BE 도메인/Assistant tool은 **사용자 권한 범위 내**에서만 데이터 접근.
- 동의(consent) 관리: IoT 텔레메트리 수집·LLM 컨텍스트 활용에 대한 사용자 동의 상태를 Identity가 관리.

### 10.2 관측성 (Observability)
- **분산 추적**: OpenTelemetry로 FE→BFF→BE→외부/LLM 전 구간 trace 연결.
- **로깅**: 구조화 로그 + 개인정보 마스킹. LLM 입출력/tool 호출 별도 감사 로그.
- **메트릭/알림**: 외부 의존성 에러율·지연, LLM 토큰/비용·지연, 고장감지 처리 지연.

### 10.3 회복성/안정성
- 서킷 브레이커·타임아웃·재시도·bulkhead (§7.1).
- 비동기 처리의 멱등성·재처리(DLQ, dead-letter queue).
- LLM 장애 시 graceful degradation: 어시스턴트 불가 시에도 기본 기능(검색·주문·접수)은 정상 동작.

### 10.4 데이터/정합성
- **DB-per-service** + 서비스 간은 이벤트/API로만 통신(직접 DB 공유 금지).
- 도메인 간 일관성은 **사가(Saga) / Outbox** 로 결과적 일관성 보장(특히 고장→구매/수리 흐름).

---

## 11. 인프라 (AKS)

- **AKS** 위에 도메인 서비스/BFF를 컨테이너로 배포. 네임스페이스로 도메인 경계 분리.
- **Ingress**: Azure Application Gateway / NGINX Ingress. 외부는 BFF/게이트웨이만 노출, BE는 내부 전용.
- **서비스 간 통신**: 서비스 메시(예: Istio/Linkerd) 또는 mTLS로 내부 트래픽 보호.
- **비동기**: Service Bus(명령/작업 큐) + Event Hubs(고볼륨 텔레메트리).
- **시크릿/키**: Azure Key Vault (PG 키, Azure OpenAI 키, SmartThings 자격증명).
- **데이터**: Azure DB for PostgreSQL(트랜잭션계), Cosmos DB(고볼륨/유연 스키마), Azure Cache for Redis(세션/캐시), Azure AI Search(검색/RAG).
- **LLM**: Azure OpenAI를 프라이빗 엔드포인트로 연결, 용도별 deployment 분리(경량 라우팅 / 메인 추론).
- **CI/CD**: GitHub Actions → ACR → AKS (배포). IaC는 Bicep/Terraform.

---

## 12. 단계별 구축 로드맵 (제안)

1. **Phase 0 — 기반**: Identity(SSO), monorepo, AKS/네트워크/CI-CD 골격, 도메인 서비스 스켈레톤.
2. **Phase 1 — 커머스 코어**: Catalog/Commerce + BFF 홈/상세/주문 화면. (수익 핵심)
3. **Phase 2 — A/S & IoT**: Service(A/S 접수), Device(보유기기/텔레메트리), 고장감지 파이프라인.
4. **Phase 3 — 어시스턴트**: Assistant Orchestrator + 읽기 전용 tool → 이후 액션 tool(확인 플로우).
5. **Phase 4 — O2O**: 매장 예약/상담 기록, 상품 상세 연계.
6. **Phase 5 — 고도화**: 이상탐지 정교화, 비용 최적화, 개인화 추천.

---

## 13. 핵심 설계 결정 요약 (ADR 후보)

| # | 결정 | 이유 |
|---|------|------|
| 1 | 도메인별 마이크로서비스 + DB-per-service | 3개 이질 도메인의 독립 확장/배포 |
| 2 | LLM 오케스트레이션은 BE에 배치 | 부수효과·트랜잭션·감사 일관성 |
| 3 | LLM 연동을 Assistant Orchestrator + Tool Gateway로 분리, 도메인 API를 tool로 호출 (DB 직접 접근 금지) | 추론과 액션 권한 분리, 인가·검증·감사 단일 관문화 |
| 4 | 되돌리기 어려운 액션은 Human-in-the-loop 확인 | 잘못된 결제/접수 방지 |
| 5 | 텔레메트리는 이벤트 기반(Event Hubs) | 고볼륨·비동기·백프레셔 |
| 6 | 외부 연동은 ACL/Adapter로 격리 | 외부 스키마 오염 방지, 교체 용이 |
| 7 | BFF는 화면 조합·스트리밍 중계만 | 책임 경계 명확화 |
| 8 | FE monorepo로 웹/모바일 로직 공유 | TS 도메인 타입·클라이언트 재사용 |

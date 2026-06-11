# 다이어그램 모음 (Diagrams)

> 기반 문서의 구조를 시각화한 **모음(derived)** 이다. 단일 출처는 각 기반 문서이며,
> 본 문서는 클래스·시퀀스·상태·흐름 다이어그램을 모은다. GitHub가 ` ```mermaid ` 블록을 렌더한다.
> LLM은 특정 모델에 종속되지 않게 **provider-agnostic** 으로 표기한다.

목차: [BE 클래스](#be--클래스) · [BE 시퀀스](#be--시퀀스) · [BE 상태](#be--상태) · [공통](#공통) · [FE](#fe)

---

## BE — 클래스

### 도메인 클래스

```mermaid
classDiagram
  direction LR
  class User {
    +Id id
    +str display_name
    +list~Id~ linked_device_ids
  }
  class Device {
    +Id id
    +str model
    +str status
    +dict metrics
  }
  class Consumable {
    +str name
    +float life_remaining
    +float threshold
  }
  class Anomaly {
    +AnomalyType type
    +Severity severity
    +str detail
  }
  class Solution {
    +bool escalation_needed
  }
  class SolutionStep {
    +int order
    +str instruction
  }
  class Source {
    +str title
    +str ref
  }
  class Part {
    +str sku
    +int price
    +bool in_stock
  }
  class Order {
    +OrderStatus status
  }
  class OrderItem {
    +int qty
  }
  class Booking {
    +Id slot_id
  }
  class Conversation {
    +int version
  }
  class Message {
    +Role role
    +str text
  }
  class Template {
    +str kind
    +dict data
  }
  class Cta {
    +CtaType type
  }
  class FlowState {
    +str name
    +str step
  }
  class Warranty {
    +bool in_warranty
    +Coverage scope
  }
  User "1" --> "*" Device : owns
  Device "1" --> "0..1" Warranty : covered_by
  User "1" --> "*" Conversation
  User "1" --> "*" Order
  Device "1" --> "*" Consumable
  Device "1" --> "*" Anomaly
  Anomaly "1" --> "*" Solution : resolved_by
  Solution "1" --> "*" SolutionStep
  Solution "1" --> "*" Source
  Solution "*" --> "*" Part : requires
  Order "1" --> "*" OrderItem
  OrderItem --> Part
  Booking --> Order
  Conversation "1" --> "*" Message
  Conversation --> FlowState
  Message --> Template
  Message "1" --> "*" Cta
```

상세 필드·불변식: `docs/data-model.md §3`.

### 서비스 · Port · 어댑터 (Mock↔실 교체 패턴)

```mermaid
classDiagram
  direction LR
  class Orchestrator
  class DeviceService
  class KnowledgeService
  class OrderService
  class DevicePort {
    <<interface>>
    +get_status()
    +detect_anomalies()
  }
  class OrderPort {
    <<interface>>
    +add_to_cart()
    +checkout()
  }
  class MockDevicePort
  class RealDevicePort
  class MockOrderPort
  Orchestrator --> DeviceService
  Orchestrator --> KnowledgeService
  Orchestrator --> OrderService
  DeviceService --> DevicePort
  OrderService --> OrderPort
  DevicePort <|.. MockDevicePort
  DevicePort <|.. RealDevicePort
  OrderPort <|.. MockOrderPort
```

모든 Port는 `Mock*`(MVP)/`Real*`(후속)을 의존성 주입으로 교체. 상세: `docs/data-model.md §6`.

### 예외 계층

```mermaid
classDiagram
  DomainError <|-- NotFoundError
  DomainError <|-- ValidationError
  DomainError <|-- ConflictError
  DomainError <|-- ConsentError
  DomainError <|-- PortError
  DomainError <|-- ConfirmationRequired
```

---

## BE — 시퀀스

### 메인 플로우 (이상 감지 → 해결 → 주문)

```mermaid
sequenceDiagram
  autonumber
  actor U as 사용자
  participant FE
  participant API as API/표현
  participant O as 오케스트레이터
  participant LLM as LLM
  participant DEV as DevicePort
  participant CS as CSKnowledgePort(RAG)
  U->>FE: "세탁기 소리나요" (+사진)
  FE->>API: WS /chat user_message
  API->>O: 함수 호출
  O->>LLM: 의도 분류(구조화 출력)
  LLM-->>O: TROUBLESHOOT
  O->>DEV: get_status / detect_anomalies
  DEV-->>O: Device, Anomaly(오류코드)
  O->>CS: find_solutions (RAG)
  CS-->>O: Solution + Source
  O->>LLM: 응답 생성(템플릿, 스트리밍)
  LLM-->>O: device_status + guide_steps + product_card
  O-->>API: delta/template/done
  API-->>FE: 스트림 청크
  FE-->>U: 렌더 + [장바구니][주문] CTA
```

### 주문 확인 게이트 (R17)

```mermaid
sequenceDiagram
  autonumber
  actor U as 사용자
  participant FE
  participant API
  participant GATE as ActionGatePort
  participant ORD as OrderPort
  U->>FE: [주문] CTA
  FE->>API: POST /orders (confirmed=false)
  API->>GATE: requires_confirmation?
  GATE-->>API: true
  API-->>FE: 409 + confirmation 템플릿
  U->>FE: [결제하기]
  FE->>API: POST /orders (confirmed=true)
  API->>ORD: checkout (멱등)
  ORD-->>API: Order(CONFIRMED)
  API-->>FE: order_summary + status_tracker
```

### 선제 알림 (R5/R20)

```mermaid
sequenceDiagram
  autonumber
  participant SCH as 임계치 감지
  participant NOTI as 알림 서비스
  participant ALERT as AlertPort
  participant FE
  SCH->>NOTI: 소모품 수명 < threshold
  NOTI->>NOTI: opted_in 확인(R20)
  alt opted_in = true
    NOTI->>ALERT: deliver(Notification)
    ALERT-->>FE: 인앱 알림(home_summary)
  else opted_in = false
    NOTI--xNOTI: 발송 안 함
  end
```

### 핸드오프 · 방문 예약 (R18)

```mermaid
sequenceDiagram
  autonumber
  actor U as 사용자
  participant FE
  participant API
  participant H as HandoffPort
  U->>FE: [방문 예약] CTA
  FE->>API: GET /bookings/slots
  API->>H: list_slots(user_id)
  H-->>API: [BookingSlot]
  API-->>FE: booking 템플릿(슬롯)
  U->>FE: 슬롯 선택 → [예약 확정]
  FE->>API: POST /bookings {slot_id, context_ref}
  API->>H: book_slot (멱등)
  H-->>API: Booking
  API-->>FE: status_tracker(예약 진행)
```

### 복합 질문 분해 (R7)

```mermaid
flowchart TD
  Q["복합 입력: '소리나고, 필터도 주문해줘'"] --> C[의도 분류·분해<br/>하이브리드]
  C --> I1[TROUBLESHOOT]
  C --> I2[ORDER]
  I1 --> P{우선순위<br/>안전·CS 먼저}
  I2 --> P
  P --> S1[1. 해결 가이드 처리]
  S1 --> S2[2. 주문 처리]
  S2 --> R[섹션 묶음 응답<br/>unhandled은 text 안내]
```

### 흐름 전환 · 복원 (R6)

```mermaid
sequenceDiagram
  autonumber
  actor U as 사용자
  participant O as 오케스트레이터
  participant S as SessionRepository
  U->>O: (해결 흐름 진행 중) "다른 거 물어볼게"
  O->>O: 주제 전환 감지
  O->>S: active_flow → suspended_flow 보관
  O-->>U: 자유 대화 응답
  U->>O: "아까 그거 계속"
  O->>S: suspended_flow 복원 → active
  O-->>U: 이전 단계부터 이어서
```

### 멀티모달 업로드 (R10)

```mermaid
sequenceDiagram
  autonumber
  actor U as 사용자
  participant FE
  participant API
  U->>FE: [＋] 카메라/갤러리
  FE->>FE: 권한 요청
  alt 권한 허용
    FE->>FE: 압축·크기/형식 검증(Media)
    FE->>API: WS user_message(text + media[])
    API-->>FE: 스트림 응답
  else 권한 거부
    FE-->>U: 텍스트 입력 폴백(R13)
  end
```

---

## BE — 상태

### 주문(Order) 전이

```mermaid
stateDiagram-v2
  [*] --> DRAFT : add_to_cart
  DRAFT --> CONFIRMED : checkout + 확인(R17)
  DRAFT --> FAILED : 결제 실패
  CONFIRMED --> [*]
  FAILED --> [*]
```

### 대화 흐름 (FlowState, R6)

```mermaid
stateDiagram-v2
  [*] --> idle
  idle --> troubleshoot : 증상 입력
  idle --> order : 주문 의도
  troubleshoot --> order : 부품 필요
  troubleshoot --> suspended : 주제 전환
  order --> suspended : 주제 전환
  suspended --> troubleshoot : 복원
  suspended --> order : 복원
  troubleshoot --> idle : 완료
  order --> idle : 완료
```

### WebSocket 연결 상태

```mermaid
stateDiagram-v2
  [*] --> connecting
  connecting --> connected : open + 토큰 검증
  connecting --> error : 실패
  connected --> streaming : /chat 응답
  streaming --> connected : done
  connected --> background : 앱 백그라운드
  background --> reconnecting : 복귀
  connected --> reconnecting : 끊김
  reconnecting --> connected : 성공
  reconnecting --> offline : 실패 누적
  offline --> reconnecting : 네트워크 복구
  error --> reconnecting : 재시도
```

---

## 공통

### 시스템 컨텍스트 (외부 시스템 경계)

```mermaid
flowchart TB
  U([사용자]) --> APP[삼성 AI 컨시어지 앱]
  APP --> BE[FastAPI 백엔드<br/>오케스트레이터 + 도메인]
  BE --> LLMP[LLM provider]
  BE --> ST[SmartThings]
  BE --> O2O[O2O 주문/결제]
  BE --> CS[CS 지식/매뉴얼]
  BE --> CAT[제품/부품 카탈로그]
  BE --> AUTH[삼성 계정 SSO]
  BE -. MVP Mock .-> O2O
  BE -. 실데이터 일부 .-> ST
  BE -. 실데이터 일부 .-> CS
  BE -. 실데이터 일부 .-> CAT
```

### RAG 데이터 흐름 (DFD)

```mermaid
flowchart LR
  Q[질문 / 이상] --> R[retrieve<br/>CS 지식 검색]
  KB[(CS 지식<br/>벡터·키워드)] --> R
  R --> A[augment<br/>근거 컨텍스트 주입]
  A --> G[generate<br/>LLM 답변]
  G --> T[출처 표기<br/>TrustPort]
  T --> OUT[guide_steps + sources]
  R -. 검색 실패 .-> FB[폴백 / 핸드오프 R13·R18]
```

### 폴백 / 예외 결정 흐름 (R13)

```mermaid
flowchart TD
  E{예외 유형} --> P[PortError<br/>외부 실패]
  E --> C[ConfirmationRequired<br/>R17]
  E --> N[NotFound / Validation]
  E --> CO[ConsentError R19]
  P --> PF[부분 degradation<br/>최소 text 응답 R13]
  P --> ESC{반복·심각?}
  ESC -->|예| HO[핸드오프 유도 R18]
  C --> CF[confirmation 템플릿 재확인]
  N --> NF[사용자 안내 + 재시도]
  CO --> CD[동의 범위 안내 / 거부]
```

### 오케스트레이션 파이프라인 (Reactive)

```mermaid
flowchart LR
  A[수신] --> B[의도 분류·분해]
  B --> C[흐름 반영 FlowState]
  C --> D{tool 선택}
  D --> E[Port / DB / compute 실행]
  E --> F[근거 보강 RAG]
  F --> G[Template 생성]
  G --> H[스트리밍 전달]
```

### 선제(Proactive) 파이프라인

```mermaid
flowchart LR
  T["기기 텔레메트리<br/>(폴링 / 이벤트)"] --> M[이상·임계치 판정]
  M --> N[알림 생성·집약]
  N --> F{빈도·중요도<br/>R26}
  F --> PRI[우선순위·다중기기<br/>R27]
  PRI --> G{옵트인·동의<br/>R20·R19}
  G -->|허용| A[AlertPort 전달]
  G -->|거부| X[발송 안 함]
  A --> U[사용자]
  U -. 탭 → reactive .-> CHAT["/chat"]
```

> 상세: `docs/architecture.md` §10 · `scenarios.md` §4-B.

---

## FE

### 사용자 여정 (User Journey)

```mermaid
journey
  title 이상 알림 → 해결 → 주문
  section 발견
    홈 선제 알림 확인: 4: 사용자
    알림 탭 → 채팅 진입: 4: 사용자
  section 진단·해결
    증상 입력(+사진): 3: 사용자
    가이드 단계 따라하기: 4: 사용자, 어시스턴트
  section 주문
    부품 후보 확인: 3: 사용자
    장바구니 → 결제 확인: 4: 사용자
    주문 완료·상태 추적: 5: 사용자
```

### 화면 네비게이션 플로우

```mermaid
flowchart LR
  Home[홈 S1] -->|채팅 FAB| Chat[채팅 패널 S3]
  Home -->|바로가기| Support[CS S2]
  Support -->|증상/모델로 찾기| Chat
  Support -->|상담/방문| Chat
  Chat -->|CTA 제품| Product[제품/부품]
  Chat -->|CTA 주문| Cart[장바구니/결제]
  Chat -->|CTA 예약| Booking[방문 예약]
  Push((푸시 알림 R20)) -. 딥링크 .-> Chat
  Push -. 딥링크 .-> Home
```

### 컴포넌트 트리 + 상태 관리

```mermaid
flowchart TD
  App --> Nav[Navigation]
  Nav --> Home[홈]
  Nav --> Support[CS]
  Nav --> ChatPanel[채팅 패널]
  ChatPanel --> MsgList[MessageList]
  MsgList --> Renderer[TemplateRenderer<br/>kind→컴포넌트 레지스트리]
  Renderer --> T1[guide_steps]
  Renderer --> T2[product_card]
  Renderer --> T3[choices ...]
  ChatPanel --> Input[InputBar + 멀티모달]
  Input --> Transport[ChatTransport<br/>WebSocket]
  ChatPanel --> US[UI·세션 store<br/>패널·FlowState]
  MsgList --> SS[서버상태<br/>쿼리/캐시]
  Transport --> SS
```

### 메시지 렌더 파이프라인 (WS 청크 → 렌더)

```mermaid
flowchart LR
  WS[WS 청크] --> D{type}
  D -->|delta| ACC[텍스트 누적]
  D -->|template| TPL[Template 추가]
  D -->|flow| FL[FlowState 배지 갱신]
  D -->|done| FIN[메시지 확정 + ctas]
  D -->|error| FB[폴백 템플릿 표시 R13]
  ACC --> RENDER[리렌더]
  TPL --> RENDER
  FIN --> RENDER
```

> 트랜스포트 연결 상태 머신은 [BE 상태 → WebSocket 연결 상태](#websocket-연결-상태) 참조(동일 채널).

# ADR-0022: 스트리밍 트랜스포트 = WebSocket (vs SSE / chunked fetch)

- **상태**: 채택
- **관련**: `docs/frontend-architecture.md` §5, `docs/api-contract.md` §2.1

## 배경
`/chat` 점진 응답(R14) + 인터랙션 회신(R6·R7) + 향후 실시간(상담원 R18·라이브 알림 R20)을 어떤 트랜스포트로 할지.

## 후보안
| 안 | 장점 | 단점 |
|---|---|---|
| **WebSocket (선택)** | 양방향(회신·중단·타이핑), RN **내장 지원** 성숙, 연결 상태 명확, 실시간 확장 용이 | 재연결·하트비트·백그라운드 관리, 스케일 시 sticky |
| SSE | 단방향 단순·프록시 친화·자동 재연결 | **RN `EventSource` 기본 미지원**(폴리필), 단방향 → 회신 채널 이원화 |
| chunked fetch | 추가 프로토콜 불필요 | **RN `fetch` ReadableStream 불안정**(엔진/버전 의존) |

## 결정
**WebSocket.** UI·상태는 **`ChatTransport` 인터페이스**에만 의존(`WebSocketTransport` 우선, SSE/HttpStream은 후보) → 교체 가능.

## 기각 이유
- **SSE**: RN 기본 미지원 + 단방향이라 회신 채널이 이원화(구조 복잡). 단방향만 필요해지면 재고.
- **chunked fetch**: RN 스트리밍 `fetch` 지원이 불안정 → 리스크 큼.

## 결과/영향
WS 스파이크(재연결·백그라운드·단절)로 보정 예정. 트랜스포트 추상화 덕에 결정 번복 시 구현만 교체.

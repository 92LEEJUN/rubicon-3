# 요구사항 (Requirements) — frontend-companion (컴패니언 FE)

## 개요

백엔드 컴패니언(이어가기 resume·미해결 스레드 open-loop·선제 재관여·메모리/컴팩션)은 구현·테스트되었고
엔드포인트도 존재한다(`docs/api-contract.md` §2.1·§2.2, `specs/always-present-companion/`). 이 스펙은 그
경험을 **React Native 앱에서 어떻게 표현·인터랙션할지**를 정의한다. 구체적으로 ① 패널 open 시 **이어가기(resume)
카드**, ② **미해결 스레드(open-loop) UI**, ③ **선제 재관여 배너**, ④ `/chat` WS의 **증분 스트리밍 표시**를
다룬다. 모든 표현은 트랜스포트 추상화(`ChatTransport`, `frontend-architecture.md` §5) 위에서 동작하고,
폴백·오프라인(R13)과 동의 게이트(R19)를 준수한다. 공유 계약(템플릿·API·데이터 모델)은 기반 문서를 따르며
여기서 재정의하지 않는다.

## 요구사항 목록

### 요구사항 1: 패널 open 시 이어가기(resume) 카드 표시

**User Story:**
사용자로서, 전역 채팅 패널을 (재)열었을 때 이전 맥락 요약과 시간감을 곧바로 보길 원한다,
그래서 매번 처음부터 설명하지 않고 자연스럽게 이어갈 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 사용자가 전역 채팅 패널을 (재)열 때 THEN FE는 `GET /resume`를 호출하고 응답(`ResumePayload`)의
   `has_context`가 true이면 이전 맥락 요약(`summary`)을 담은 **이어가기 카드**를 패널 상단에 렌더해야 한다 (SHALL).
2. WHEN resume 응답에 `elapsed_label`이 있을 때 THEN FE는 상대 시간 표현(예: "어제")을 카드에 표시해야 한다 (SHALL).
3. WHEN `ResumePayload`에 `open_loops[]`가 있을 때 THEN FE는 이어가기 카드 안에 미해결 스레드 목록을 우선순위 순서로 표시해야 한다 (SHALL).
4. WHEN 이어가기 카드를 표시할 때 THEN FE는 **'이어가기'** 와 **'새로 시작'** 두 행동을 제공해야 한다 (SHALL).
5. WHEN 사용자가 '새로 시작'을 선택할 때 THEN FE는 `fresh` 파라미터로 새 흐름을 시작하고 이전 맥락 요약을 화면에서 제거해야 한다 (SHALL).
6. IF `ResumePayload.has_context`가 false(첫 방문·맥락 없음)이면 THEN FE는 이어가기 카드를 표시하지 않고 깨끗한 빈 상태로 시작해야 한다 (SHALL).

### 요구사항 2: 미해결 스레드(open-loop) UI와 해소/닫기 액션

**User Story:**
사용자로서, 진행 중이던 일(미해결 이슈·진행 주문·보류 흐름)을 패널에서 보고 챙기거나 정리하길 원한다,
그래서 놓친 일을 이어가거나 더는 필요 없는 항목을 치울 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN open-loop 목록을 표시할 때 THEN FE는 각 항목의 종류(`kind`)·요약·우선순위를 구분해 렌더해야 한다 (SHALL).
2. WHEN 사용자가 open-loop 항목을 탭할 때 THEN FE는 해당 `ref` 맥락으로 대화를 이어 `/chat`에 재진입해야 한다 (SHALL).
3. WHEN 사용자가 open-loop를 해소(resolve) 또는 닫기(dismiss)할 때 THEN FE는
   `POST /open-loops/{ref}/{action}`(`action`=`resolve|dismiss`)을 호출해야 한다 (SHALL).
4. WHEN 해소/닫기 호출이 성공할 때 THEN FE는 해당 항목을 목록에서 제거(또는 상태 갱신)하고 즉시 UI에 반영해야 한다 (SHALL).
5. IF 해소/닫기 호출이 `404` 또는 실패를 반환하면 THEN FE는 항목을 제거하지 않고 오류 안내·재시도를 제공해야 한다 (SHALL).

### 요구사항 3: 선제 재관여 배너 표시 및 대화 전이

**User Story:**
사용자로서, 중요한 후속(부품 입고·해결확인 시점 등)을 에이전트가 먼저 알려주길 원한다,
그래서 신경 쓰지 않아도 제때 챙길 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 앱/홈 진입 또는 적절한 시점에 THEN FE는 `GET /reengagement`를 조회하고 비어있지 않은 `ReEngagement`
   응답이 있으면 **선제 재관여 배너**(`primary_label`·`message`·`also_count`)를 노출해야 한다 (SHALL).
2. WHEN 배너가 노출될 때 THEN FE는 `POST /reengagement/deliver`로 전달을 확정해 동일 메시지의 재노출을 억제해야 한다 (SHALL).
3. WHEN 사용자가 배너를 탭할 때 THEN FE는 `primary_ref` 맥락으로 `/chat`에 재진입(proactive→reactive)해 대화를 이어야 한다 (SHALL).
4. IF `/reengagement` 응답이 `{}`(없음)이면 THEN FE는 배너를 노출하지 않아야 한다 (SHALL).
5. WHEN 사용자가 배너를 닫을(dismiss) 때 THEN FE는 해당 배너를 숨기고 다시 노출하지 않아야 한다 (SHALL).

### 요구사항 4: 증분 스트리밍 표시

**User Story:**
사용자로서, 답변이 생성되는 즉시 점진적으로 나타나길 원한다,
그래서 기다리는 동안에도 진행감을 느끼고 빠르게 읽기 시작할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN `/chat` WS에서 `delta` 청크가 도착할 때 THEN FE는 해당 텍스트를 진행 중 메시지에 즉시 누적·렌더해야 한다 (SHALL).
2. WHEN `section` 청크가 도착할 때 THEN FE는 섹션을 우선순위(도착) 순서대로 **세로 스택**으로 점진 렌더해야 한다 (SHALL).
3. WHILE 응답을 수신 중일 때 THEN FE는 **타이핑 인디케이터**를 표시해야 한다 (SHALL).
4. WHEN `flow` 청크가 도착할 때 THEN FE는 `active_flow`를 FlowState에 반영해야 한다 (SHALL).
5. WHEN `done` 청크가 도착할 때 THEN FE는 누적된 섹션으로 메시지를 확정하고 타이핑 인디케이터를 제거해야 한다 (SHALL).
6. WHEN 진행 문구를 표시할 때 THEN FE는 **답변 중심**의 진행 표현만 보이고 내부 시스템·대기 상태는 노출하지 않아야 한다 (SHALL).

### 요구사항 5: 트랜스포트 추상화 위 동작 및 폴백/오프라인 (R13)

**User Story:**
사용자로서, 네트워크가 불안정하거나 일부 데이터가 실패해도 대화가 통째로 끊기지 않길 원한다,
그래서 안내를 받고 다시 시도하거나 가능한 부분만이라도 볼 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN resume·open-loop·reengagement·스트리밍을 처리할 때 THEN FE는 `ChatTransport` 인터페이스(WS 구현)와
   결정적 HTTP 클라이언트에만 의존하고, 구체 트랜스포트에 직접 결합하지 않아야 한다 (SHALL).
2. WHEN `/chat` WS에서 `error` 청크가 도착할 때 THEN FE는 `fallback` 템플릿으로 렌더하고 대화를 중단하지 않아야 한다 (SHALL).
3. IF 오프라인이거나 연결이 끊긴 상태이면 THEN FE는 오프라인 안내와 재연결/재시도 경로를 제공해야 한다 (SHALL).
4. IF resume 또는 open-loop 조회가 부분 실패하면 THEN FE는 가능한 부분(예: 요약만)을 degraded 상태로 표시해야 한다 (SHALL).

### 요구사항 6: 동의 게이트 — 선제/개인화 비노출 (R19)

**User Story:**
사용자로서, 동의하지 않은 선제·개인화 표현이 내 화면에 나타나지 않길 원한다,
그래서 내 프라이버시 범위 안에서만 컴패니언 경험이 동작한다.

**수용기준 (Acceptance Criteria):**
1. IF 사용자가 선제/개인화에 동의(`Consent`/`opted_in`)하지 않았다면 THEN FE는 선제 재관여 배너를 노출하지 않고
   `/reengagement` 조회를 게이트해야 한다 (SHALL).
2. IF 동의가 없거나 철회되면 THEN FE는 이어가기 카드의 개인화 요약을 제한하거나 비노출해야 한다 (SHALL).
3. WHEN 동의 상태가 변경될 때 THEN FE는 현재 노출 중인 선제/개인화 표현을 즉시 갱신(필요 시 제거)해야 한다 (SHALL).

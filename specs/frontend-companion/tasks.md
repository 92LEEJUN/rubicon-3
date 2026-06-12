# 작업 (Tasks) — frontend-companion (컴패니언 FE)

> `design.md` 를 실제 구현으로 나눈 체크리스트.
> 각 항목은 작고 검증 가능한 단위로 쪼개고, 끝에 관련 요구사항 번호를 표기한다.
> 완료한 항목은 `[x]` 로 체크한다.

## 작업 목록

- [x] 1. 타입·계약 연결 _(요구사항 1, 2, 3, 4)_
  - [x] 1.1 `types/`에 `ResumePayload`·`OpenLoop`·`ReEngagement`·`ChatResponseChunk`·`MessageSection` DTO 대응 타입 정렬(재정의 금지, data-model/api-contract 참조)
  - [x] 1.2 결정적 HTTP 클라이언트(`api/`)에 `/resume`(`?fresh`)·`/reengagement`·`/reengagement/deliver`·`/open-loops/{ref}/{action}` 메서드 추가

- [x] 2. 상태 환원 — `chatReducer` 스트리밍 누적 _(요구사항 4)_
  - [x] 2.1 `delta` 청크 → 진행 메시지 텍스트 누적
  - [x] 2.2 `section` 청크 → 섹션 리스트 도착 순서대로 push(세로 스택)
  - [x] 2.3 `flow` 청크 → `active_flow`를 FlowState에 반영
  - [x] 2.4 `done` 청크 → 누적 섹션으로 메시지 확정 + 타이핑 종료
  - [x] 2.5 `error` 청크 → `fallback` 템플릿 삽입, 대화 미중단
  - [x] 2.6 reducer 단위 테스트(시퀀스 delta→section(순서)→flow→done/error)

- [x] 3. `companion` store(Zustand) — 가시성 상태 _(요구사항 1, 3, 5)_
  - [x] 3.1 `panelOpen`·`resumeVisibility(shown|dismissed)`·`bannerState(hidden|shown|dismissed)`·화면 맥락 정의

- [x] 4. `useResume` 훅 _(요구사항 1, 5, 6)_
  - [x] 4.1 패널 open 시 `GET /resume` 조회·캐시(React Query)
  - [x] 4.2 `startFresh()` — `fresh=true` 재호출 + resume 가시성 `dismissed`
  - [x] 4.3 `has_context=false` 시 카드 미표시(빈 상태) 처리
  - [x] 4.4 동의 미동의 시 개인화 요약 제한/비노출(게이트)
  - [x] 4.5 부분 실패 시 요약만 degraded 노출

- [x] 5. `ResumeCard` 컴포넌트 _(요구사항 1, 5, 6)_
  - [x] 5.1 `summary` + `elapsed_label`(상대시간) 렌더
  - [x] 5.2 '이어가기'/'새로 시작' 두 액션 제공
  - [x] 5.3 `OpenLoopList`를 카드 안에 우선순위 순서로 임베드
  - [x] 5.4 degraded·빈 상태 처리
  - [x] 5.5 컴포넌트 테스트(요약·시간·목록·액션·빈상태)

- [x] 6. `useOpenLoops` 훅 + `OpenLoopList`/`OpenLoopItem` _(요구사항 2)_
  - [x] 6.1 `kind`·요약·우선순위 구분 렌더
  - [x] 6.2 항목 탭 → `useChat.resumeFromRef(ref)`로 `/chat` 재진입
  - [x] 6.3 `resolve`/`dismiss` → `POST /open-loops/{ref}/{action}`(낙관적 갱신)
  - [x] 6.4 성공 시 목록 즉시 반영, `404`/실패 시 롤백 + 재시도 안내
  - [x] 6.5 컴포넌트·훅 테스트(resolve·dismiss·실패 롤백·탭 재진입)

- [x] 7. `useReEngagement` 훅 + `ReEngagementBanner` _(요구사항 3, 6)_
  - [x] 7.1 `GET /reengagement` 조회, `{}`면 미노출
  - [x] 7.2 노출 시 `POST /reengagement/deliver`로 재노출 억제
  - [x] 7.3 `primary_label`·`message`·`also_count` 배너 렌더
  - [x] 7.4 탭 → `primary_ref`로 `/chat` 재진입(proactive→reactive)
  - [x] 7.5 닫기(dismiss) → 숨김 + 재노출 안 함
  - [x] 7.6 동의 미동의 시 조회/노출 게이트(no-op)
  - [x] 7.7 컴포넌트·훅 테스트(노출·`deliver`·탭·닫기·`{}`미노출·게이트)

- [x] 8. `StreamingMessage` 컴포넌트 _(요구사항 4)_
  - [x] 8.1 `delta` 누적 텍스트 + `section` 세로 스택 렌더(템플릿 렌더러 §4 재사용)
  - [x] 8.2 수신 중 타이핑 인디케이터 표시, `done` 시 제거
  - [x] 8.3 미처리(`handled:false`) 섹션 라벨 표시, 모르는 kind → `text` 폴백
  - [x] 8.4 진행 문구는 답변 중심만(내부 시스템·대기 비노출)
  - [x] 8.5 컴포넌트 테스트(섹션 스택·타이핑·done 확정·폴백)

- [x] 9. `useChat` 재진입 진입점 _(요구사항 2, 3)_
  - [x] 9.1 `resumeFromRef(ref, screen_context?)` — 맥락 주입 후 `/chat` send

- [x] 10. 트랜스포트 독립·폴백·오프라인 _(요구사항 5)_
  - [x] 10.1 UI/훅이 `ChatTransport` 인터페이스·HTTP 클라이언트에만 의존(구체 결합 금지) 확인
  - [x] 10.2 오프라인/연결 끊김 안내 + 재연결/재시도 경로(연결 상태머신 연동)
  - [x] 10.3 stub 트랜스포트 주입으로 트랜스포트 독립 검증(계약 stub, api-contract §5)

- [x] 11. 동의 게이트 일관성 _(요구사항 6)_
  - [x] 11.1 `useConsent`를 선제·개인화 표현 훅(`useResume`·`useReEngagement`)에 연결
  - [x] 11.2 동의 상태 변경 시 노출 중 선제/개인화 표현 즉시 갱신(필요 시 제거)
  - [x] 11.3 게이트 테스트(미동의 시 조회·배너·개인화 요약 비노출, 변경 시 즉시 갱신)

## 진행 메모
<!-- 구현 중 설계와 달라진 점, 결정 사항 등을 기록한다. 변경 시 design.md도 갱신한다. -->

- **상태관리 라이브러리 미설치 → 경량 React로 동등 구현.** design은 ADR-0023(React Query + Zustand)을
  참조하나, 실제 `frontend/package.json`에는 두 라이브러리가 없고 코드베이스는 plain React
  (`useState`/`useReducer`/`useEffect`, `useHomeData` 류)로 동작한다. 새 의존성을 추가하지 않고
  **동일 역할**을 경량으로 구현했다: 조회/캐시=`useResume`·`useReEngagement`(useEffect 패칭),
  가시성 store=`state/companionStore.ts`(모듈 스토어+구독 훅), 동의 게이트=`state/useConsent.tsx`
  (Context+모듈 스토어). 계약·동작은 design과 동일(조회=쿼리, 액션=mutation+갱신, 스트림=reducer).
- **증분 스트리밍 reducer는 기존 `chatReducer`가 이미 충족** — delta/section/flow/done/error를
  api-contract §2.1 봉투대로 환원하고 있었다(작업 2는 보강·테스트만 추가). 스트리밍 표현은
  기존 ChatPanel 인라인 뷰를 재사용 가능한 `components/StreamingMessage.tsx`로 추출.
- **재진입(resumeFromRef)** — 새 BE 계약 없이 기존 `user_message` 봉투에 `screen_context.resume_ref`로
  ref 맥락을 주입(open-loop·배너 탭 공용). BFF가 ref를 해석해 proactive→reactive로 잇는다(통합 시 확인 필요).
- **open-loop `summary` 필드** — 표시용 요약은 BE OpenLoop에 명시되지 않았으나 목록 라벨에 필요해
  `summary?`(옵셔널)로 두었다. 없으면 `ref`를 폴백 표시. BFF가 채워주면 그대로 노출(계약 추가 아님).

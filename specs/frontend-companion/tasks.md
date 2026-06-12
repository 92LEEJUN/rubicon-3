# 작업 (Tasks) — frontend-companion (컴패니언 FE)

> `design.md` 를 실제 구현으로 나눈 체크리스트.
> 각 항목은 작고 검증 가능한 단위로 쪼개고, 끝에 관련 요구사항 번호를 표기한다.
> 완료한 항목은 `[x]` 로 체크한다.

## 작업 목록

- [ ] 1. 타입·계약 연결 _(요구사항 1, 2, 3, 4)_
  - [ ] 1.1 `types/`에 `ResumePayload`·`OpenLoop`·`ReEngagement`·`ChatResponseChunk`·`MessageSection` DTO 대응 타입 정렬(재정의 금지, data-model/api-contract 참조)
  - [ ] 1.2 결정적 HTTP 클라이언트(`api/`)에 `/resume`(`?fresh`)·`/reengagement`·`/reengagement/deliver`·`/open-loops/{ref}/{action}` 메서드 추가

- [ ] 2. 상태 환원 — `chatReducer` 스트리밍 누적 _(요구사항 4)_
  - [ ] 2.1 `delta` 청크 → 진행 메시지 텍스트 누적
  - [ ] 2.2 `section` 청크 → 섹션 리스트 도착 순서대로 push(세로 스택)
  - [ ] 2.3 `flow` 청크 → `active_flow`를 FlowState에 반영
  - [ ] 2.4 `done` 청크 → 누적 섹션으로 메시지 확정 + 타이핑 종료
  - [ ] 2.5 `error` 청크 → `fallback` 템플릿 삽입, 대화 미중단
  - [ ] 2.6 reducer 단위 테스트(시퀀스 delta→section(순서)→flow→done/error)

- [ ] 3. `companion` store(Zustand) — 가시성 상태 _(요구사항 1, 3, 5)_
  - [ ] 3.1 `panelOpen`·`resumeVisibility(shown|dismissed)`·`bannerState(hidden|shown|dismissed)`·화면 맥락 정의

- [ ] 4. `useResume` 훅 _(요구사항 1, 5, 6)_
  - [ ] 4.1 패널 open 시 `GET /resume` 조회·캐시(React Query)
  - [ ] 4.2 `startFresh()` — `fresh=true` 재호출 + resume 가시성 `dismissed`
  - [ ] 4.3 `has_context=false` 시 카드 미표시(빈 상태) 처리
  - [ ] 4.4 동의 미동의 시 개인화 요약 제한/비노출(게이트)
  - [ ] 4.5 부분 실패 시 요약만 degraded 노출

- [ ] 5. `ResumeCard` 컴포넌트 _(요구사항 1, 5, 6)_
  - [ ] 5.1 `summary` + `elapsed_label`(상대시간) 렌더
  - [ ] 5.2 '이어가기'/'새로 시작' 두 액션 제공
  - [ ] 5.3 `OpenLoopList`를 카드 안에 우선순위 순서로 임베드
  - [ ] 5.4 degraded·빈 상태 처리
  - [ ] 5.5 컴포넌트 테스트(요약·시간·목록·액션·빈상태)

- [ ] 6. `useOpenLoops` 훅 + `OpenLoopList`/`OpenLoopItem` _(요구사항 2)_
  - [ ] 6.1 `kind`·요약·우선순위 구분 렌더
  - [ ] 6.2 항목 탭 → `useChat.resumeFromRef(ref)`로 `/chat` 재진입
  - [ ] 6.3 `resolve`/`dismiss` → `POST /open-loops/{ref}/{action}`(낙관적 갱신)
  - [ ] 6.4 성공 시 목록 즉시 반영, `404`/실패 시 롤백 + 재시도 안내
  - [ ] 6.5 컴포넌트·훅 테스트(resolve·dismiss·실패 롤백·탭 재진입)

- [ ] 7. `useReEngagement` 훅 + `ReEngagementBanner` _(요구사항 3, 6)_
  - [ ] 7.1 `GET /reengagement` 조회, `{}`면 미노출
  - [ ] 7.2 노출 시 `POST /reengagement/deliver`로 재노출 억제
  - [ ] 7.3 `primary_label`·`message`·`also_count` 배너 렌더
  - [ ] 7.4 탭 → `primary_ref`로 `/chat` 재진입(proactive→reactive)
  - [ ] 7.5 닫기(dismiss) → 숨김 + 재노출 안 함
  - [ ] 7.6 동의 미동의 시 조회/노출 게이트(no-op)
  - [ ] 7.7 컴포넌트·훅 테스트(노출·`deliver`·탭·닫기·`{}`미노출·게이트)

- [ ] 8. `StreamingMessage` 컴포넌트 _(요구사항 4)_
  - [ ] 8.1 `delta` 누적 텍스트 + `section` 세로 스택 렌더(템플릿 렌더러 §4 재사용)
  - [ ] 8.2 수신 중 타이핑 인디케이터 표시, `done` 시 제거
  - [ ] 8.3 미처리(`handled:false`) 섹션 라벨 표시, 모르는 kind → `text` 폴백
  - [ ] 8.4 진행 문구는 답변 중심만(내부 시스템·대기 비노출)
  - [ ] 8.5 컴포넌트 테스트(섹션 스택·타이핑·done 확정·폴백)

- [ ] 9. `useChat` 재진입 진입점 _(요구사항 2, 3)_
  - [ ] 9.1 `resumeFromRef(ref, screen_context?)` — 맥락 주입 후 `/chat` send

- [ ] 10. 트랜스포트 독립·폴백·오프라인 _(요구사항 5)_
  - [ ] 10.1 UI/훅이 `ChatTransport` 인터페이스·HTTP 클라이언트에만 의존(구체 결합 금지) 확인
  - [ ] 10.2 오프라인/연결 끊김 안내 + 재연결/재시도 경로(연결 상태머신 연동)
  - [ ] 10.3 stub 트랜스포트 주입으로 트랜스포트 독립 검증(계약 stub, api-contract §5)

- [ ] 11. 동의 게이트 일관성 _(요구사항 6)_
  - [ ] 11.1 `useConsent`를 선제·개인화 표현 훅(`useResume`·`useReEngagement`)에 연결
  - [ ] 11.2 동의 상태 변경 시 노출 중 선제/개인화 표현 즉시 갱신(필요 시 제거)
  - [ ] 11.3 게이트 테스트(미동의 시 조회·배너·개인화 요약 비노출, 변경 시 즉시 갱신)

## 진행 메모
<!-- 구현 중 설계와 달라진 점, 결정 사항 등을 기록한다. 변경 시 design.md도 갱신한다. -->

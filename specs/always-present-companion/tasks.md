# 작업 (Tasks) — always-present companion

> `design.md`를 구현 단위로 나눈 체크리스트. 끝에 요구사항 번호 표기. 완료는 `[x]`.
> 토대(메모리 ADR-0040)는 선행 의존 — 컴팩션 구현이 먼저거나 병행.

## 0. 선행 (토대)
- [x] 0.1 `ConversationMemory`(summary·facts·summarized_through) 모델 + **user 단위** Repository(인메모리·삭제 cascade) _(ADR-0040, 요구 4·6)_ — `app/domain/models.py`·`app/repositories/conversation_memory.py`
- [x] 0.2 `CompactionService` — N턴 트리거 + 롤링 요약 + 사실 추출(주문ID·오류코드) + rehydrate(`working_context`). 결정적 `RuleBasedCompactor` _(ADR-0040)_ — `app/compaction.py`, 테스트 `tests/test_compaction.py`
  - 손실 위험 항목(주문ID·오류코드)은 facts로 보존 ✓ (기기모델·동의는 명시 facts로)
- [x] 0.3 `LLMCompactor` 실 요약 + **구조화 facts 추출 스키마**(`_FACTS_SCHEMA`: devices·unresolved_issues, 규칙 사실과 이중 보존) + **토큰 임계 트리거**(`CompactionService.max_tokens` 70% 모드) — `app/compaction.py`
  - 남은: 실 모델별 토큰 budget 설정·평가셋 튜닝(컨테이너는 기본 N턴 모드 유지)
- [x] 0.4 오케스트레이터 턴 루프 배선 — 턴 후 `record_turn`(→`maybe_compact`), 다음 턴에 `context()`(요약+사실) **LLM 주입** — `app/companion.py`·`api/internal.py`(`_stream_and_record`)·`orchestrator/legacy.py`(`_memory_note`)
  - 사실은 **매 턴 즉시 추출**(최근 턴 사실 누락 방지), 요약은 임계 시 컴팩션

## 1. Resume (이어가기) _(요구 1·4·5)_
- [x] 1.1 `CompanionService.resume(user_id)` → `ResumePayload`(summary·facts·elapsed·suspended_flow) + `GET /internal/resume`·BFF `/resume` _(요구 1·4)_
- [x] 1.2 영속 메모리 기반 복원 — working 세션과 무관하게 user 메모리에서 _(요구 1.2)_
- [x] 1.3 `elapsed_label` 상대 시간(방금·어제·지난주) _(요구 5)_
- [x] 1.4 '새로 시작' 분기(`fresh=true`, 메모리 비주입) _(요구 1.3)_
- [ ] 1.5 패널 open(R9) 시 resume 템플릿 노출(FE) + `suspended_flow` 소스(FlowState 영속) 연결

## 2. OpenLoop (미해결 스레드) _(요구 2)_
- [x] 2.1 `OpenLoop` 모델 + `InMemoryOpenLoopRepository`(ref 멱등·상태·우선순위) — `app/repositories/open_loop.py`
- [x] 2.2 생성 훅 — 사실(오류코드·주문ID)에서 자동 멱등 생성(`_sync_open_loops`), 오류>주문 우선순위 _(요구 2.1)_
- [~] 2.3 해소 — `resolve_loop`/`dismiss_loop` 서비스 + "해소된 건 안 되살림". **남은**: R25 해결확인·주문 배송완료 이벤트 연결 _(요구 2.3)_
- [x] 2.4 resume에 열린 loop 우선순위 정렬 포함(`ResumePayload.open_loops`) _(요구 2.2)_

## 3. ReEngagement (선제, 엄격 게이트) _(요구 3·6)_
- [ ] 3.1 트리거 — open-loop 후속(입고·R25 시점·리마인드) 이벤트/스케줄
- [ ] 3.2 **엄격 게이트** — Consent/opted_in → R26 빈도/중요도 → 가치/중복 억제 → R27 묶음 _(요구 3.2·3.3·6.1)_
- [ ] 3.3 통과분 AlertPort 전달(§10) + 탭 시 proactive→reactive 맥락 이어가기 _(요구 3.4)_
- [ ] 3.4 게이트 차단 결정적 테스트(동의 없음·빈도 초과·저가치·중복)

## 4. 교차기기 / 프라이버시 _(요구 4·6)_
- [ ] 4.1 메모리·open-loop **user 단위 키** + Consent 접근 가드 _(요구 4.2·6.1)_
- [ ] 4.2 삭제 요청 시 메모리·open-loop cascade _(요구 6.2, R19)_

## 5. 계측 / 검증
- [ ] 5.1 분석 이벤트 — resume·open-loop 제시/해소·선제 전달·탭(analytics.md 택소노미 정합)
- [ ] 5.2 통합 시나리오 — 진단 미완료 → 재방문 resume → 부품 입고 선제 → 탭 이어가기

## 진행 메모
- 구현 중 설계와 달라지면 `design.md`/관련 ADR 갱신. 선제 자세는 ADR-0042 준수(엄격 게이트).

# 작업 (Tasks)

> [design.md](./design.md) 를 실제 구현으로 나눈 체크리스트. 전환 전략 = **스트랭글러**.
> 각 단계는 작고 검증 가능하게 쪼개고, 끝에 관련 요구사항 번호를 표기한다. 완료 시 `[x]`.
> **불변 원칙:** 매 단계 후 "LLM 전부 off = 기존 `core.Orchestrator` 봉투 동일" 회귀가 green이어야 다음 단계로 간다.

## 작업 목록

- [ ] 1. capability 골격 + 레지스트리 _(요구사항 1, 2)_
  - [ ] 1.1 `backend/app/orchestrator/capability.py` 신규 — `Capability` dataclass(`name·kind·intents·emits·needs·priority·tools·prompt·run`), `CapabilityFn` 타입.
  - [ ] 1.2 `registry.py` — `CapabilityRegistry`(`{name: Capability}`, `catalog()`는 name·intents·needs·설명만). _(요구사항 1-4)_
  - [ ] 1.3 `TurnCtx`(블랙보드) — `write/read`, 스코프 주입. `carried_parts` 일반형. _(요구사항 4)_

- [ ] 2. 결정적 tool capability 래핑 (1차 이주) _(요구사항 2-3, 8-2)_
  - [ ] 2.1 `handlers.handle_*`(device_status·troubleshoot·order·recommend·general)을 `kind=tool` capability로 감싸 `MessageSection`→`{"type":"section"}` 방출.
  - [ ] 2.2 troubleshoot capability는 `required_parts`를 `ctx.write`, order capability는 `needs=("required_parts",)`로 `ctx.read`(기존 carry 정합). _(요구사항 4-2, 4-3)_
  - [ ] 2.3 등록: 각 capability를 레지스트리에 엔트리로. _(요구사항 1-2)_

- [ ] 3. 룰 플래너 + 검증 _(요구사항 3)_
  - [ ] 3.1 `rule_plan(intents)` — `core._ordered_intents`+`plan_workers` 매핑을 `Plan{steps[...]}`로(우선순위·depends_on 포함). _(요구사항 3-3)_
  - [ ] 3.2 `PlanValidator.validate` — 미등록 capability·사이클 제거, `priority` 위상정렬, 무효시 `None`. _(요구사항 3-2)_
  - [ ] 3.3 주문 등 되돌릴 수 없는 의도 규칙 가드레일 재검증. _(요구사항 3-4)_

- [ ] 4. CapabilityOrchestrator 조립 (결정적 경로 패리티) _(요구사항 6, 8)_
  - [ ] 4.1 `astream(message, screen_context, memory)` — plan(룰)→execute(순차, depends_on)→merge→done. `astream_multiagent`와 동일 시그니처.
  - [ ] 4.2 다단계 스트리밍 — 빠른 결정적 capability(device_status) 먼저 방출(첫 섹션 ≤2~3s). _(요구사항 6-1, 6-2)_
  - [ ] 4.3 `parallel_group` 표기만, 실행 순차(ADR-0017). _(요구사항 3-5)_
  - [ ] 4.4 **회귀 게이트** — LLM off에서 기존 `test_orchestrator.py`(J1·compound·envelope·fallback)를 새 경로로 통과. _(요구사항 10-5, 8-2)_

- [ ] 5. agent capability 래핑 (2차 이주) _(요구사항 2-3·2-4·2-5)_
  - [ ] 5.1 Diagnosis·Commerce·Recommend를 `runtime._run_worker(prompt, msg, allowed)` 위에 `kind=agent` capability로 감싸 delta(설명)+section 방출.
  - [ ] 5.2 모든 LLM 호출 `achat_completion`(async·세마포어·백오프) 경유, 순차 유지. _(요구사항 7 정합)_
  - [ ] 5.3 포함/금지 규율 프롬프트 검증(근거·출처 R16·위험 R23·추천근거 R8 / 날조·시스템문구·R19·무확인커밋). _(요구사항 2-4, 2-5)_

- [ ] 6. LLM 플래너 _(요구사항 3-1)_
  - [ ] 6.1 `LLMPlanner.propose(catalog, message, ctx)` 구조화 출력 `Plan`, `achat_completion` 경유, 주입형.
  - [ ] 6.2 propose→validate→무효/실패면 `rule_plan` 폴백 배선. _(요구사항 3-3, 9-2)_

- [ ] 7. 하이브리드 병합 _(요구사항 5)_
  - [ ] 7.1 결정적 section 우선순위 스택 보존 + 연결 delta만 얇은 LLM(섹션 사실 불변).
  - [ ] 7.2 복합(R7) handled/unhandled 구분. _(요구사항 5-4)_

- [ ] 8. 조건부 리뷰 + 커밋 안전 _(요구사항 7)_
  - [ ] 8.1 `should_review(intents, safety, uncertain)` 재사용 — 안전·커밋·불확실만 발동. _(요구사항 7-1, 7-2)_
  - [ ] 8.2 커밋 = `confirmation` section + ActionGate(409), 스트림 버퍼링 없음. _(요구사항 7-3)_
  - [ ] 8.3 위반시 보정/차단·사람연결, 재계획 루프 금지. _(요구사항 7-4)_

- [ ] 9. 디스패치 수렴 + 토글 _(요구사항 8)_
  - [ ] 9.1 `internal.py` `_stream_turn`을 capability 경로로 흡수, 토글을 capability 단위 LLM-backed로 평가(매 호출 env). _(요구사항 8-1, 8-4)_
  - [ ] 9.2 어느 토글 상태든 §2.1 봉투 동일 보장. _(요구사항 8-3)_
  - [ ] 9.3 패리티 증명 후 `legacy.astream_turn`·`runtime.astream_multiagent`·`core.Orchestrator` 옛 경로 제거(스트랭글러 마무리).

- [ ] 10. 실패·부분 폴백 _(요구사항 9)_
  - [ ] 10.1 step별 try/except·타임아웃 — 실패 step만 폴백/생략, 부분결과 유지. _(요구사항 9-1)_
  - [ ] 10.2 플래너 실패→룰 폴백, 턴 회복불가→`error` 봉투(비중단). _(요구사항 9-2, 9-3)_

- [ ] 11. Mock/결정적 테스트 _(요구사항 10)_
  - [ ] 11.1 플래너 plan 스텁 주입 — 검증·폴백(미등록·사이클·빈 plan) 단언. _(요구사항 10-1, 10-2)_
  - [ ] 11.2 블랙보드 핸드오프(`required_parts` write→read) 단언(기존 계승). _(요구사항 10-3)_
  - [ ] 11.3 스트리밍·병합 청크 종류·순서 단언(기존 계승). _(요구사항 10-4)_
  - [ ] 11.4 토글 수렴 회귀 — LLM 전부 off = 결정적 봉투 동등. _(요구사항 10-5)_

## 진행 메모
- 스트랭글러 순서: **1→2→3→4(결정적 패리티 게이트)** 까지가 "회귀 없이 골격 수렴" 1차. 이후 **5~8**에서 LLM capability·플래너·병합·리뷰를 얹고, **9.3**에서 옛 경로 삭제로 마무리.
- 기존 자산 재사용: `_PRIORITY`·`plan_workers`·`carried_parts`·`should_review`·`_run_worker`·`achat_completion`. 새로 만들지 말고 재배치.
- 구현 중 설계와 달라지면 design.md·본 파일 동시 갱신(루트 CLAUDE.md 규칙).

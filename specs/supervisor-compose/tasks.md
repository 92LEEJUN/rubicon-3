# 작업 (Tasks) — 슈퍼바이저 응답 종합(Compose) + 병렬 가드레일

> `design.md` 구현 체크리스트. 완료 항목은 `[x]`.

## 작업 목록

- [x] 1. ADR·기반 문서 _(요구사항 1·2·3·4)_
  - [x] 1.1 ADR-0053(슈퍼바이저 plan+compose 양끝) + ADR-0054(가드레일 병렬·fail-closed) 작성, 인덱스 갱신
  - [x] 1.2 `docs/orchestration.md`·`docs/agents.md`에 슈퍼바이저 종합·병렬 가드레일 반영
  - [x] 1.3 `docs/response-templates.md`에 내러티브(text 재사용·composed 플래그) 주석 _(요구사항 4-1)_

- [x] 2. 가드레일 에이전트 _(요구사항 2·3)_
  - [x] 2.1 `orchestrator/guardrail.py` — `Verdict`·`Guardrail.screen/ascreen`(인젝션·남용 규칙)
  - [x] 2.2 `Guardrail.check`(PII 마스킹, 텍스트만) + `refusal_section`
  - [x] 2.3 결정적 단위 테스트(block·통과·마스킹)

- [x] 3. 슈퍼바이저 compose _(요구사항 1)_
  - [x] 3.1 `prompts.COMPOSER_PROMPT`(BASE_POLICY + 종합 지침, 데이터 재생성 금지)
  - [x] 3.2 `LLMPlanner.compose`/`acompose`(facts→내러티브)
  - [x] 3.3 stub 기반 결정적 테스트

- [x] 4. 오케스트레이터 배선 _(요구사항 1·2·3·4)_
  - [x] 4.1 토글 `compose_on()`/`guardrail_on()` + 생성자 `guardrail` 주입
  - [x] 4.2 `_screen_and_route`(gather 병렬, screen 예외→block, R2-1·R2-3)
  - [x] 4.3 `astream`에 pre(block 시 refusal·스킵)→capability→barrier→compose(스킵 조건·실패 폴백)→post 배선
  - [x] 4.4 `_section_facts`·`_narration_section` + 봉투 §2.1 유지(R4-2)
  - [x] 4.5 `internal.py` `_build_cap_orch`에 `Guardrail()` 주입

- [x] 5. 검증 _(요구사항 1~4)_
  - [x] 5.1 `tests/test_compose.py` 전 항목 + 기존 스위트 회귀 green
  - [x] 5.2 ruff 클린
  - [x] 5.3 `verify_compose_timing.py` — 총 E2E·first-token 측정(off vs on)

## 진행 메모
- 내러티브는 신규 계약 없이 `text` kind 재사용 → FE/BFF 변경 불필요(intent="narration").
- compose/guardrail은 **astream(async)** 에만. 동기 경로·토글 off는 회귀 불변.
- 2-track(카드 선-전송) 및 텍스트 섹션 접기는 후속 최적화(design 결정 참조).

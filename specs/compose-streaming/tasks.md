# 작업 (Tasks) — compose 2-track 스트리밍 + 차단 시 라우팅 취소

> `design.md` 구현 체크리스트. 완료 항목은 `[x]`.

## 작업 목록

- [x] 1. ADR·문서 _(요구사항 1·2·3)_
  - [x] 1.1 ADR-0055(2-track 스트리밍 + 라우팅 취소) + 인덱스, ADR-0053 스트리밍 항목에 0055 참조
  - [x] 1.2 `docs/orchestration.md` §11 갱신(배리어 해체·2-track·delta 내러티브)

- [x] 2. 스트리밍 compose + 마스킹 공개 _(요구사항 2)_
  - [x] 2.1 `LLMPlanner.acompose_stream`(OpenAI stream=True, 토큰 델타 yield)
  - [x] 2.2 `Guardrail.mask` 공개(기존 `_mask_text` 승격), `check`는 유지

- [x] 3. 오케스트레이터 2-track 재배선 _(요구사항 1·2·4)_
  - [x] 3.1 카드 섹션 선-방출(가드레일 on이면 check 후) → first-token = 라우팅 홉
  - [x] 3.2 `_emit_narration` — 처리 ≥2 분기(off=스트리밍 delta / on=버퍼+마스킹 delta), 실패 무방출
  - [x] 3.3 `_narration_section` 제거(내러티브는 delta로 일원화)
  - [x] 3.4 봉투 순서 `section* → delta? → flow → done` 보장

- [x] 4. 차단 시 라우팅 취소 _(요구사항 3)_
  - [x] 4.1 `_screen_and_route` task 기반 — block 시 route task `cancel()`

- [x] 5. 검증 _(요구사항 1~4)_
  - [x] 5.1 `tests/test_compose_streaming.py` + 기존 `test_compose.py` 갱신(narration→delta)
  - [x] 5.2 전 스위트 회귀 green + ruff 클린
  - [x] 5.3 `verify_multiturn_timing.py` 갱신 — first-token 회복·차단 턴 단축 측정

## 진행 메모
- 내러티브는 더 이상 `narration` 섹션이 아니라 `delta`(기존 계약) → FE/BFF 변경 없음.
- guardrail on 경로는 안전 위해 버퍼링(점진성 양보). 스트리밍-세이프 마스킹은 후속.

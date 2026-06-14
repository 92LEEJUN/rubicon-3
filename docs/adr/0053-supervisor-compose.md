# ADR-0053: LLM 플래너를 "슈퍼바이저(plan + compose 양끝)"로 승격

- **상태**: 채택
- **관련**: [`specs/supervisor-compose/`](../../specs/supervisor-compose/requirements.md), [orchestration.md](../orchestration.md), [agents.md](../agents.md)(§1 슈퍼바이저·§3 조건부 리뷰), [response-templates.md](../response-templates.md), ADR-0046(capability 분리·CTA 게이팅), ADR-0048(LLM 플래너 단일 라우터), ADR-0044(추천 reasoning), ADR-0054(병렬 가드레일)

## 배경
capability 오케스트레이터(②, ADR-0046·0048)에서 LLM 플래너는 **라우팅만** 한다 — `capabilities[]`와
`out_of_scope[]`만 고르고, 실제 섹션은 각 capability 핸들러(`handle_*`)가 **독립적으로** 결정론으로
생성한다. 장점은 환각 억제·계약 안정·결정적 테스트지만, 복합 턴(예: 진단+주문+추천)에서 응답이
**카드들의 단순 나열**이 되어 문맥을 잇는 "한 사람의 목소리"가 없다. 멀티에이전트 경로(①,
`runtime.astream_multiagent`)에는 워커 산출을 모으는 슈퍼바이저 조립 개념이 있었으나, ②로 수렴하며
그 reduce(종합) 단계가 빠졌다.

## 결정
**LLM 플래너를 슈퍼바이저로 승격**해 턴의 **양 끝**을 같은 주입체가 담당하게 한다.

- **Phase A — plan(의도 추출)**: 기존 `propose`/`apropose`. 변경 없음(ADR-0048).
- **Phase B — compose(응답 종합)**: 신규 `compose`/`acompose(message, plan, facts)`. 핸들러가 만든
  섹션의 **facts 요약**을 받아 **하나의 자연어 내러티브**를 생성한다. 같은 모델·클라이언트·persona
  (BASE_POLICY)를 공유 → 일관된 목소리, plan 문맥 보유.
- **불변식: 말만 생성, 데이터는 그대로.** compose는 **내러티브(자연어)만** 만든다. 카드·CTA·게이팅·
  data 필드 등 **구조화 출력은 핸들러 원본을 변형 없이** 통과시킨다. LLM이 CTA kind·가격·id를
  재생성하면 게이팅·계약 불변식이 조용히 깨지므로 금지. 내러티브는 카드를 "참조"만 한다.
- **선택적·폴백.** 처리된 섹션이 2개 미만(또는 clarify·out_of_scope뿐)이면 compose를 **스킵**(종합할 게
  없음, 비용 절감). compose 실패 시 **원본 섹션으로 폴백**(턴 붕괴 금지).
- **토글·회귀 불변.** `COMPOSE` env off면 종합 없이 오늘과 동일(스트랭글러). compose는 비동기 서빙
  경로(`astream`)에만 얹고, 동기 경로는 불변. compose는 LLM 호출이므로 `LLM_BACKED` 위에서만 동작.
- **계약 추가 없음.** 내러티브는 **기존 `text` 템플릿** 재사용(`intent="narration"`,
  `data.composed=true`). FE/BFF 신규 렌더러 불필요.

> **정련(→ ADR-0055).** 아래 "내러티브 선두 섹션(배리어)" 방출 방식은 **ADR-0055에서 2-track 스트리밍**
> (카드 선-방출 + 내러티브 `delta`)으로 정련됐다. compose 개념·불변식(말만 생성·데이터 불변)은 유지되고
> **방출 방식만** 바뀐다. 내러티브는 더 이상 `narration` 섹션이 아니라 `delta`로 나간다.

## 대안 / 기각
- **별도 Composer 워커(독립 주입체)** — 종합을 플래너와 분리된 에이전트로. 그러나 plan 문맥을 다시
  전달해야 하고 주입체·수명주기가 하나 더 늘며, "같은 두뇌가 양끝"이라는 일관성 이점을 잃는다.
  **기각** — 슈퍼바이저 한 주체가 plan+compose를 갖는 편이 단순·정합.
- **핸들러 prose를 내러티브로 대체(텍스트 섹션 접기)** — 중복은 줄지만 `coverage` 등 구조 필드가
  사라져 FE 로직이 깨질 위험. **후속 보류** — v1은 내러티브 선두 + 원본 섹션 유지(데이터 보존 우선).
- **모든 응답을 자유 LLM 텍스트로(멀티에이전트 ① 회귀)** — 환각·계약 불안정으로 ②에서 이미 기각된
  방향. **기각** — "데이터는 결정론, 말은 LLM" 원칙 유지.

## 영향
- **orchestration.md** — ② 흐름에 슈퍼바이저 종합(reduce) 단계 추가(배리어·선택적·폴백).
- **agents.md** — 슈퍼바이저가 **양끝(분해+조립)** 을 갖는 그림 명시. 조립=compose.
- **response-templates.md** — 내러티브는 text 재사용(composed 플래그), 신규 kind 없음.
- **레이턴시** — 종합은 배리어(전 섹션 수집) + LLM 1콜 → **first-token·총 E2E 증가**. 사용자 승인 사항.
  단일 섹션·실패 시 비용 없음(스킵·폴백).
- **가드레일 정합** — ADR-0054의 출력 post-check가 내러티브 포함 방출 직전에 선다.

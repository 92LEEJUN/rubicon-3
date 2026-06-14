# 설계 (Design) — compose 2-track 스트리밍 + 차단 시 라우팅 취소

> `requirements.md`(요구사항 1~4)를 만족시킨다. compose/가드레일 기반은
> [ADR-0053](../../docs/adr/0053-supervisor-compose.md)·[ADR-0054](../../docs/adr/0054-guardrail-parallel.md),
> 본 변경 근거는 [ADR-0055](../../docs/adr/0055-compose-2track-streaming.md).

## 개요
v1의 "배리어 후 내러티브 선두 섹션"을 **2-track**으로 바꾼다 — 결정적 카드 섹션을 compose 완료 전에
먼저 흘리고(first-token = 라우팅 홉), 내러티브는 뒤따라 **`delta`로 스트리밍**한다. FE는 이미 한 턴에서
`delta`(자연어) + `section`(카드)을 함께 렌더하고 delta를 별도 슬롯(인트로)에 누적하므로 **계약·FE
변경이 없다**. 가드레일 차단 시 병렬 라우팅 task를 **취소**해 낭비를 없앤다.

## 아키텍처

```
사용자 메시지
   │
   ├── screen(task) ∥ aroute(task)         ← 병렬 시작(ADR-0054)
   │      └ screen=block ──► aroute.cancel() ──► refusal 섹션 → flow → done   (요구사항 3)
   ▼ screen=allow
 plan ──► _run_capabilities(결정적·빠름) ──► 카드 섹션[]
   │
   │  ── 카드 먼저 방출(2-track, 요구사항 1) ──
   ▼  (guardrail on이면 카드 post-check 후) yield section* …          ◄ first-token = 라우팅 홉
   │
   ▼  처리 섹션 ≥2 + compose 가능 ?
        ├ guardrail off → acompose_stream(...) → yield {delta, tok}*   (점진, 요구사항 2-1)
        └ guardrail on  → text=await acompose(...); text=mask(text)
                          → yield {delta, text}                        (버퍼·마스킹, 요구사항 2-2)
        실패 → 내러티브 생략(카드로 완결, 요구사항 4-1)
   ▼
 yield flow → done    (봉투: section* → delta? → flow → done, 요구사항 4-3)
```

## 주요 컴포넌트 / 인터페이스

- **`LLMPlanner`** — compose에 스트리밍 변형 추가 _(요구사항 2)_:
  - `acompose_stream(message, plan, facts) -> AsyncIterator[str]` — OpenAI `stream=True`로 토큰 델타를
    yield. 기존 `acompose`(완성 문자열)는 **guardrail on 버퍼 경로**용으로 유지.
- **`Guardrail`** — `mask(text) -> str` 공개(기존 `_mask_text` 승격) _(요구사항 2-2)_. `check`(섹션)는 유지.
- **`CapabilityOrchestrator.astream`** — 2-track 재배선 _(요구사항 1·2·4)_:
  - 카드 섹션 먼저 방출(가드레일 on이면 `check` 후). 그다음 내러티브를 delta로.
  - 내러티브 emit 헬퍼 `_emit_narration(message, plan, sections, mask)` — 처리 섹션 <2면 무방출,
    스트리밍/버퍼 분기, 실패 시 무방출(카드로 완결).
  - `_screen_and_route`를 **task 기반**으로 — `create_task(screen)`·`create_task(aroute)`; screen이 block이면
    route task `cancel()` 후 `(verdict, None)` 반환(요구사항 3).
- **봉투** — `section*`(카드) → `delta*`(내러티브) → `flow` → `done`. 모두 기존 §2.1 Chunk 계약.

## 데이터 모델
- 신규 계약 **없음** _(요구사항 2-3)_. 내러티브는 `delta` 청크(기존)로. 더 이상 `narration` 섹션을 만들지
  않는다(v1의 `_narration_section` 제거). FE는 delta 누적 텍스트(assistantText)로 표시.

## 에러 처리
- **compose 스트리밍 실패**(예외·빈 출력) → 내러티브 생략, 카드만으로 done(요구사항 4-1).
- **라우팅 취소**(차단) → `CancelledError` 흡수, 차단 응답 정상 방출(요구사항 3).
- **가드레일 post 예외**(카드) → 기존대로 error 폴백(ADR-0054).
- **COMPOSE off** → 기존 경로 그대로(요구사항 4-2).

## 테스트 전략
- **단위(결정적, stub)** — `tests/test_compose_streaming.py`:
  - 2-track: 카드 `section`이 내러티브 `delta`보다 **앞**(요구사항 1-1·4-3)·카드 데이터 불변(1-3).
  - 스트리밍: guardrail off → 다수 `delta`(stub이 토큰 yield, 2-1). guardrail on → 단일 `delta` +
    PII 마스킹(2-2). 신규 섹션 kind 없음(2-3).
  - 취소: 차단 시 라우팅 stub의 apropose가 **취소되어 완료 표식이 안 찍힘**(요구사항 3-1·3-2).
  - 폴백: compose 스트리밍 예외 → 카드만 done(4-1). 단일 섹션 → 내러티브 없음.
- **회귀** — 기존 `test_compose.py`(narration 섹션 가정) 갱신: 내러티브가 이제 delta. `test_capability_async.py`·
  전 스위트 green.
- **타이밍(수동)** — `verify_multiturn_timing.py` 갱신: compose 턴 first-token이 라우팅 홉 수준으로
  내려오고, 차단 턴이 screen 수준으로 내려오는지 확인.

## 설계 결정 / 대안
- **카드-우선(내러티브는 delta 후행)** — first-token을 라우팅 홉으로 회복. FE가 delta를 별도 슬롯
  상단에 누적하므로 **방출 순서(카드 먼저)와 표시 순서(내러티브 위)가 분리** → 지연·UX 동시 충족.
  v1의 "내러티브 선두 섹션"은 이로써 갱신(ADR-0055가 ADR-0053의 스트리밍 항목을 정련).
- **guardrail on 시 버퍼링(점진성 양보)** — 토큰 경계를 가로지르는 PII는 스트리밍 마스킹이 불신뢰.
  안전(fail-closed 원칙) 우선 → on이면 완성 후 마스킹. 스트리밍-세이프 마스킹(롤링 버퍼)은 후속.
- **캐시 제외** — (message, facts) 캐시는 멀티턴 적중률 ≈0(facts가 carry에 의존). 레이턴시 레버 아님 —
  idempotency 가드로만 가치(별도). 본 스펙 비범위.
- **차단 시 라우팅 취소** — 병렬 gather는 둘 다 await해 차단 턴이 라우팅 홉을 낭비. task+cancel로 제거.

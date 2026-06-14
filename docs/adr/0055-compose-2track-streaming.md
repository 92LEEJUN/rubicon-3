# ADR-0055: compose 2-track 스트리밍 + 차단 시 라우팅 취소

- **상태**: 채택
- **관련**: [`specs/compose-streaming/`](../../specs/compose-streaming/requirements.md), ADR-0053(슈퍼바이저 compose — 본 ADR이 그 스트리밍 항목을 정련), ADR-0054(가드레일 병렬·fail-closed), [orchestration.md](../orchestration.md) §11, [response-templates.md](../response-templates.md)

## 배경
ADR-0053의 compose는 v1에서 **전 섹션 수집(배리어) 후 내러티브를 선두 섹션**으로 냈다. 그래서 복합 턴
first-token이 `라우팅 홉 + compose LLM 1콜(≈800ms)`로 묶인다. 장문 멀티턴 측정(`verify_multiturn_timing.py`)
에서 compose 턴마다 first-token이 ~1250ms로 뛰고, 멀티턴 누적은 `Σ(라우팅) + 800×(compose 턴 수)`로
compose가 지배한다. 그런데 결정적 카드 섹션은 라우팅 직후 **즉시** 만들 수 있어, compose 완료를 기다릴
이유가 없다. 또한 가드레일 차단 턴이 병렬 라우팅 홉을 낭비한다(gather가 둘 다 await).

> **캐시 기각.** "(message, facts) compose 캐시"를 검토했으나, facts가 세션 carry에 의존해 같은 문장도
> 턴마다 facts가 달라 **멀티턴 적중률 ≈0**. 레이턴시 레버가 아니라 idempotency 가드일 뿐 → 본 결정에서 제외.

## 결정
**배리어를 해체**하고 차단 낭비를 제거한다.

- **2-track 방출.** 결정적 카드 섹션을 compose 완료 **전에 먼저** 흘린다(`section*`). 내러티브는 그 뒤에
  방출 → **first-token = 라우팅 홉**(compose가 가리지 않음). 카드 데이터·CTA·게이팅은 불변(ADR-0053).
- **내러티브 = `delta` 스트리밍.** 내러티브를 더 이상 `narration` 섹션으로 만들지 않고 **기존 `delta`
  청크**로 방출한다(신규 계약 없음). FE는 한 턴에서 delta(자연어)+section(카드)을 이미 함께 렌더하고
  delta를 별도 슬롯(인트로) 상단에 누적 → **방출 순서(카드 먼저)와 표시 순서(내러티브 위)가 분리**되어
  지연·UX를 동시에 충족.
  - `GUARDRAIL` off → compose 출력을 **토큰 델타로 점진 스트리밍**(`acompose_stream`).
  - `GUARDRAIL` on → **완성 후 마스킹**하여 단일 델타로(토큰 경계 가로지르는 PII 마스킹 불신뢰 → 안전
    우선, 점진성 양보). 스트리밍-세이프 마스킹(롤링 버퍼)은 후속.
- **차단 시 라우팅 취소.** pre-screen과 라우팅을 task로 병렬 시작하되, screen이 block이면 라우팅 task를
  `cancel()` → 차단 턴이 라우팅 완료를 기다리지 않음(첫 토큰 = screen 수준, 비용도 절감).
- **폴백·회귀 불변.** compose(스트리밍 포함) 실패 → 카드만으로 완결(내러티브 생략). `COMPOSE` off면
  기존 §2.1과 동일. 봉투는 `section* → delta? → flow → done`.

## 대안 / 기각
- **내러티브 선두 섹션 유지(v1)** — 읽기 흐름은 좋지만 first-token이 compose에 묶임. FE가 delta를 상단에
  표시하므로 "카드 먼저 방출 + 내러티브 위 표시"로 둘 다 얻을 수 있어 **기각**.
- **guardrail on에서도 토큰 스트리밍** — PII가 토큰 경계로 쪼개지면 마스킹 누락. 안전 우선 → **부분 기각**
  (off만 점진 스트리밍, on은 버퍼).
- **compose 캐시** — 멀티턴 적중률 ≈0(위). **기각**(레이턴시 명목).
- **차단 시 라우팅 직렬화(screen 먼저)** — 단순하나 ADR-0054의 병렬 원칙을 깬다. task+cancel로 병렬을
  유지하면서 낭비만 제거 → 채택.

## 영향
- **orchestration.md §11** — compose 흐름을 2-track·delta 스트리밍으로 갱신. ADR-0053의 "내러티브 선두"
  항목은 본 ADR로 정련(대체 아님 — compose 개념·불변식은 유지, 방출 방식만 변경).
- **response-templates.md** — 내러티브는 `narration` 섹션이 아니라 `delta`로 표현(신규 kind 없음) 명시.
- **레이턴시** — compose 턴 first-token: ~1250ms → ~라우팅 홉. 차단 턴: ~라우팅 홉 → ~screen. 총 E2E는
  내러티브 완료까지라 유사(점진 표시로 체감 개선). 측정은 `verify_multiturn_timing.py`.
- **계약** — 추가 없음(delta 재사용). BFF/FE 변경 불필요(FE delta+section 혼합 기지원).

# 요구사항 (Requirements) — compose 2-track 스트리밍 + 차단 시 라우팅 취소

## 개요
슈퍼바이저 compose(ADR-0053)는 v1에서 **전 섹션 수집(배리어) 후 내러티브를 선두 섹션으로** 냈다.
그 결과 복합 턴 first-token이 `라우팅 홉 + compose LLM 1콜(≈800ms)`로 묶여, 장문 멀티턴에서 compose
턴마다 first-token이 ~1250ms로 뛴다(`verify_multiturn_timing.py`). 결정적 카드 섹션은 라우팅 직후
**즉시** 만들 수 있는데도 compose 완료를 기다리는 게 병목이다. 본 작업은 **배리어를 해체**한다:
결정적 카드를 먼저 흘리고(2-track) 내러티브는 뒤따라 스트리밍한다. 또한 가드레일 차단 턴이 병렬
라우팅 홉을 낭비하는 문제를 **라우팅 취소**로 없앤다. (캐시는 멀티턴 적중률이 사실상 0이라 레버에서
제외 — 분석 결과.)

## 요구사항 목록

### 요구사항 1: 2-track — 결정적 카드 선-방출
**User Story:**
사용자로서, 복합 응답에서도 카드(진단·주문·추천)를 **즉시** 보기를 원한다, 그래서 종합 문장이
완성되기를 기다리지 않아도 된다.

**수용기준 (Acceptance Criteria):**
1. WHEN `COMPOSE` on이고 처리 섹션이 2개 이상일 때 THEN 시스템은 결정적 카드 섹션을 **compose 완료
   전에 먼저** 방출해야 한다 (SHALL). first-token은 라우팅 홉 수준이어야 한다(compose가 가리지 않음).
2. WHEN 내러티브는 카드 섹션 **이후에** 방출해야 한다 (SHALL). 봉투는 `section*(카드) → (내러티브)
   → flow → done`.
3. WHILE 카드 섹션의 구조화 데이터·CTA·게이팅은 v1과 동일하게 **불변** 이어야 한다 (SHALL, ADR-0053 정합).

### 요구사항 2: 내러티브 토큰 스트리밍
**User Story:**
사용자로서, 종합 문장이 **한 번에 멈춰 있다 뜨는** 대신 점진적으로 채워지기를 원한다, 그래서 대기가
짧게 느껴진다.

**수용기준 (Acceptance Criteria):**
1. IF `GUARDRAIL` off이면 THEN 시스템은 compose 출력을 **`delta` 청크로 점진 스트리밍**해야 한다 (SHALL,
   기존 §2.1 delta 계약 재사용 — FE 변경 없음).
2. IF `GUARDRAIL` on이면 THEN 시스템은 내러티브를 **완성 후 마스킹**하여 방출해야 한다 (SHALL).
   토큰 경계를 가로지르는 PII 마스킹은 신뢰할 수 없으므로 **안전을 위해 버퍼링**한다(점진성 양보).
3. WHEN 내러티브는 `delta`로 방출하므로 **신규 계약·신규 섹션 kind가 없어야** 한다 (SHALL, FE는 delta
   누적 텍스트를 이미 렌더).

### 요구사항 3: 차단 시 라우팅 취소
**User Story:**
운영자로서, 가드레일이 입력을 차단하면 낭비되는 라우팅 LLM 호출을 **취소**하기를 원한다, 그래서
차단 턴이 빠르고 비용도 들지 않는다.

**수용기준 (Acceptance Criteria):**
1. WHEN 가드레일 pre-screen이 차단(block)을 반환할 때 THEN 시스템은 병렬로 시작한 **라우팅 task를
   취소**해야 한다 (SHALL).
2. IF 라우팅이 취소되면 THEN 차단 응답은 라우팅 완료를 **기다리지 않아야** 한다 (SHALL, 차단 턴
   first-token이 screen 수준).
3. WHEN screen이 통과(allow)면 THEN 시스템은 라우팅 결과를 정상적으로 사용해야 한다 (SHALL, 회귀 불변).

### 요구사항 4: 폴백·회귀 불변
**User Story:**
통합 담당자로서, 새 스트리밍이 실패해도 턴이 깨지지 않고, 토글 off면 기존과 같기를 원한다.

**수용기준 (Acceptance Criteria):**
1. IF compose(스트리밍 포함)가 실패하면 THEN 시스템은 **카드만으로 턴을 완결**(내러티브 생략)해야 한다
   (SHALL, 턴 붕괴 금지).
2. IF `COMPOSE` off이면 THEN 시스템은 기존(§2.1 section*→flow→done)과 **동일하게** 동작해야 한다 (SHALL).
3. WHEN 봉투 순서는 `section*` 이 항상 `flow`·`done` 앞, `delta`(내러티브)는 `section`과 `flow` 사이에
   있어야 한다 (SHALL).

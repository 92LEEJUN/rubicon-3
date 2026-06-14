# 요구사항 (Requirements) — 실험·롤아웃(Runtime A/B)

## 개요
런타임에 사용자를 결정적으로 variant에 분배하고(sticky bucketing), 그 분배에 따라
BE/FE가 분기하며, 노출(exposure)을 기존 분석 싱크에 기록하는 **실험·점진 롤아웃** 기반을
도입한다. 전부 토글 `EXPERIMENTS`(기본 off) 뒤에 두며, off면 항상 control(기존 동작)로
폴백해 회귀 불변을 보장한다(production-readiness S8, ⑭ 실험·롤아웃).

## 요구사항 목록

### 요구사항 1: 결정적·sticky 실험 할당

**User Story:**
실험 운영자로서, 같은 사용자가 항상 같은 variant에 들어가길 원한다, 그래서 일관된 경험과
믿을 만한 분석을 얻을 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 같은 `unit_id`(user_id 또는 guest 토큰)와 실험 키로 할당을 두 번 요청하면 THEN
   시스템은 **동일한 variant**를 반환해야 한다 (SHALL).
2. WHEN 한 실험에 트래픽 비율(가중치)이 정의돼 있으면 THEN 시스템은 해시 기반으로 그 비율에
   **근사 비례**하여 unit들을 variant에 분배해야 한다 (SHALL).
3. IF `unit_id`가 비어 있거나 없으면 THEN 시스템은 control(첫 variant)로 폴백해야 한다 (SHALL).

### 요구사항 2: 실험 정의 레지스트리

**User Story:**
실험 운영자로서, 실험을 키·variant·트래픽 비율로 선언하길 원한다, 그래서 코드 분기에서
실험을 일관되게 참조할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 실험을 키·variant 목록·가중치로 등록하면 THEN 시스템은 그것을 단일 레지스트리에
   보관하고 키로 조회 가능해야 한다 (SHALL).
2. IF 등록되지 않은 키로 조회하면 THEN 시스템은 control 폴백을 반환하고 예외를 던지지 않아야 한다 (SHALL).
3. WHEN 실험에 control variant가 명시되면 THEN 시스템은 그 control을 모든 폴백의 기본값으로
   사용해야 한다 (SHALL).

### 요구사항 3: 토글 게이트(EXPERIMENTS 기본 off = 회귀 불변)

**User Story:**
운영자로서, 실험 기능을 토글로 켜고 끄길 원한다, 그래서 off일 때 기존 동작이 그대로
유지(스트랭글러)되는 것을 보장할 수 있다.

**수용기준 (Acceptance Criteria):**
1. IF `EXPERIMENTS` 토글이 off이면 THEN 모든 할당은 **control**을 반환해야 한다 (SHALL).
2. WHILE 토글이 off인 동안 시스템은 exposure 이벤트를 발행하지 않아야 한다 (SHALL).

### 요구사항 4: variant 전달 — BE 헬퍼 + FE 훅

**User Story:**
개발자로서, BE와 FE 양쪽에서 동일한 규칙으로 variant를 읽길 원한다, 그래서 FE/BE 분기가
일관되게 동작할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN BE 코드가 실험 키와 unit_id로 헬퍼를 호출하면 THEN 시스템은 variant 문자열을
   반환해야 한다 (SHALL).
2. WHEN FE 컴포넌트가 `useVariant(key)`를 호출하면 THEN 훅은 해당 실험의 variant를
   반환하고, 미지정·미해결 시 control로 폴백해야 한다 (SHALL).
3. WHEN BE가 할당 엔드포인트를 노출하면 THEN FE 클라이언트는 같은 결정적 규칙의 결과를
   조회할 수 있어야 한다 (SHALL).

### 요구사항 5: 노출 로깅(exposure) — 기존 분석 싱크에 append

**User Story:**
분석가로서, 어떤 unit이 어떤 variant에 노출됐는지 알길 원한다, 그래서 실험 효과를 측정할
수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 할당이 일어나고 노출이 기록되면 THEN 시스템은 기존 분석 싱크에 `experiment_exposed`
   이벤트를 **append**(기존 이벤트·시그니처 불변)해야 한다 (SHALL).
2. WHEN 같은 unit·실험·variant 조합으로 노출을 여러 번 기록하면 THEN 시스템은 중복을
   억제(de-dup)할 수 있어야 한다 (SHALL).
3. WHEN exposure 이벤트가 기록되면 THEN props에 `experiment`·`variant`가 포함돼야 한다 (SHALL).

### 요구사항 6: 홀드아웃·점진 롤아웃(canary) 비율 게이트

**User Story:**
운영자로서, 실험을 일부 트래픽에만 점진 노출(canary)하고 일부는 홀드아웃으로 제외하길
원한다, 그래서 위험을 통제하며 롤아웃할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 실험에 rollout 비율(0.0~1.0)이 설정되면 THEN 그 비율 밖의 unit은 control(미노출)로
   처리돼야 한다 (SHALL).
2. WHEN 실험에 holdout 비율이 설정되면 THEN 그 비율의 unit은 실험에서 제외(control 고정)돼야
   한다 (SHALL).
3. WHILE rollout=0.0 인 동안 시스템은 모든 unit을 control로 처리해야 한다 (SHALL).

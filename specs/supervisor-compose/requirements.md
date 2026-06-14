# 요구사항 (Requirements) — 슈퍼바이저 응답 종합(Compose) + 병렬 가드레일

## 개요
capability 오케스트레이터(②, ADR-0046·0048)는 LLM 플래너가 **라우팅만** 하고, 각 capability
핸들러가 **독립적으로** 섹션을 뱉는다. 그래서 복합 턴(진단+주문+추천)에서 응답이 카드의 단순
나열처럼 보이고, 문맥을 잇는 "한 사람의 목소리"가 없다. 본 작업은 LLM 플래너를 **슈퍼바이저**로
승격해 턴의 **양 끝**(앞=의도 추출/plan, 뒤=응답 종합/compose)을 잡게 하고, **가드레일을 의도
추출과 병렬**로 두어 입력 안전을 직렬 지연 없이 확보한다. compose는 **자연어 내러티브만** 생성하고
카드·CTA·게이팅 등 **구조화 데이터는 재생성하지 않는다**(계약·안전 불변식 보존). 스트리밍 first-token
지연은 감수하되(사용자 승인), 전반적 응답 품질을 우선한다.

## 요구사항 목록

### 요구사항 1: 슈퍼바이저 양끝(plan + compose)
**User Story:**
사용자로서, 여러 요청이 섞인 메시지에도 카드만 나열되지 않고 **하나의 자연스럽게 정리된 응답**을 받기를
원한다, 그래서 무엇을·왜·다음에 무엇을 하면 되는지 한눈에 이해할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN `COMPOSE` 토글이 on이고 처리된(handled) 섹션이 2개 이상일 때 THEN 시스템은 같은 LLM
   슈퍼바이저(플래너와 동일 주입체)로 섹션들을 종합한 **내러티브 섹션 1개를 선두에** 두어야 한다 (SHALL).
2. WHEN compose가 실행될 때 THEN 시스템은 핸들러가 만든 **구조화 섹션(카드·CTA·게이팅·data 필드)을
   변형 없이 그대로** 유지해야 한다 (SHALL). 내러티브는 데이터를 재생성하지 않는다.
3. IF `COMPOSE` 토글이 off이면 THEN 시스템은 종합 없이 기존 §2.1 봉투(section* → flow → done)와
   **동일하게** 동작해야 한다 (SHALL, 회귀 불변).
4. IF compose LLM 호출이 실패하면 THEN 시스템은 내러티브 없이 **원본 섹션으로 폴백**해야 한다 (SHALL,
   턴 붕괴 금지).
5. IF 처리된 섹션이 1개 이하면(또는 clarify·out_of_scope뿐) THEN 시스템은 compose를 **건너뛰어야**
   한다 (SHALL, 비용 절감 — 종합할 게 없음).

### 요구사항 2: 가드레일 = 의도 추출과 병렬, fail-closed
**User Story:**
운영자로서, 프롬프트 인젝션·범위 밖 남용 입력을 응답 전에 차단하되 **추가 직렬 지연 없이** 처리하기를
원한다, 그래서 안전과 성능을 동시에 지킬 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN `GUARDRAIL` 토글이 on일 때 THEN 시스템은 가드레일 입력 검사(pre-screen)를 **의도 추출(라우팅)과
   병렬로**(asyncio.gather) 실행해야 한다 (SHALL).
2. IF 가드레일이 입력을 차단(block)하면 THEN 시스템은 capability 실행을 **건너뛰고** 안전 거부 섹션
   하나로 응답해야 한다 (SHALL, fail-closed).
3. IF 가드레일 pre-screen이 **예외**를 던지면 THEN 시스템은 이를 **차단으로 간주**해야 한다 (SHALL,
   fail-closed — 통과 금지).
4. IF `GUARDRAIL` 토글이 off이면 THEN 시스템은 가드레일을 발동하지 않고 기존과 **동일하게** 동작해야
   한다 (SHALL, 회귀 불변).
5. WHEN 가드레일 검사는 LLM 없이 **규칙(정규식·패턴)으로 결정적**이어야 한다 (SHALL, 단위 검증 가능,
   ADR-0052 정합).

### 요구사항 3: 출력 후처리(post-check)
**User Story:**
운영자로서, 최종 방출 직전 응답에 민감정보·정책 위반이 없는지 한 번 더 거르기를 원한다, 그래서
LLM 종합 출력이 들어와도 안전 경계를 유지할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN `GUARDRAIL` on일 때 THEN 시스템은 방출 직전 모든 섹션(내러티브 포함)의 텍스트에 대해
   **PII 마스킹·금지 정책 검사(post-check)** 를 수행해야 한다 (SHALL).
2. IF post-check가 예외를 던지면 THEN 시스템은 미검증 내용을 그대로 내보내지 않고 **안전 오류 폴백**으로
   대체해야 한다 (SHALL, fail-closed 정합).
3. WHEN post-check는 구조화 데이터(카드 식별자·가격 등 계약 필드)를 **훼손하지 않고** 텍스트 메시지만
   대상으로 해야 한다 (SHALL).

### 요구사항 4: 계약·관측 정합
**User Story:**
통합 담당자로서, 내러티브가 들어와도 FE/BFF 계약이 깨지지 않기를 원한다, 그래서 3계층이 조용히 어긋나지
않는다.

**수용기준 (Acceptance Criteria):**
1. WHEN 내러티브 섹션은 **기존 `text` 템플릿 kind**를 재사용해야 한다 (SHALL, FE 신규 렌더러 불필요 —
   계약 추가 없음). intent="narration", data에 `prose`/`composed` 플래그를 둔다.
2. WHEN 봉투는 기존 §2.1(section* → flow → done, 실패 시 error)을 **그대로** 유지해야 한다 (SHALL).

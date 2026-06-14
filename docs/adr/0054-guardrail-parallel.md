# ADR-0054: 가드레일을 "의도 추출과 병렬 + fail-closed"로 배선

- **상태**: 채택
- **관련**: [`specs/supervisor-compose/`](../../specs/supervisor-compose/requirements.md), [`specs/trust-safety-baseline/`](../../specs/trust-safety-baseline/requirements.md), ADR-0052(가드레일을 별도 에이전트로 — 구조 결정), ADR-0053(슈퍼바이저 compose), [llm-policy.md](../llm-policy.md), [agents.md](../agents.md), [operations.md](../operations.md)

## 배경
ADR-0052는 신뢰·안전을 **별도 가드레일 에이전트(입력 pre / 출력 post 2-단계)** 로 둔다는 **구조**를
결정했다. 본 ADR은 그 가드레일을 capability 오케스트레이터(②)에 **어떻게 배선**할지 — 특히 입력
검사를 의도 추출과 직렬로 둘지 병렬로 둘지, 그리고 검사 실패(예외) 시 통과/차단 정책 — 을 정한다.
입력 검사를 라우팅 앞에 직렬로 두면 안전하지만 모든 턴에 검사 지연이 더해진다.

## 결정
- **입력 검사(pre)는 의도 추출(라우팅)과 병렬.** `asyncio.gather(guardrail.ascreen, orchestrator.aroute)`
  로 동시에 실행한다. 가드레일은 **결정적 규칙(정규식·패턴)** 이라 빠르고 LLM 라우팅 홉 뒤에 지연이
  숨는다 → **직렬 지연 0**. 차단(block)이면 capability 실행을 건너뛰고 안전 거부로 응답한다(라우팅
  결과는 폐기).
- **fail-closed.** pre-screen이 **예외**를 던지면 **차단으로 간주**한다(통과 금지). 안전은 모호할 때
  보수적으로 막는다.
- **출력 검사(post)는 방출 직전.** 내러티브(ADR-0053) 포함 모든 섹션 **텍스트**에 PII 마스킹·금지
  정책을 적용한다. **구조화 계약 필드(가격·id 등)는 훼손하지 않는다**(텍스트만 대상). post-check가
  예외면 미검증 내용을 내보내지 않고 **§2.1 error 폴백**으로 대체(fail-closed 정합).
- **토글·회귀 불변.** `GUARDRAIL` env off면 미발동 = 오늘과 동일(스트랭글러). 비동기 서빙 경로
  (`astream`)에만 얹고 동기 경로는 불변.
- **결정적·테스트 가능.** LLM 없이 규칙 기반 → 단위 검증(ADR-0052 정합). `Guardrail`은 오케스트레이터에
  주입(기본 결정적 인스턴스).

## 대안 / 기각
- **직렬 pre(라우팅 앞에 검사)** — 단순하나 모든 턴에 검사 지연이 더해진다. 검사가 결정적·경량이라
  병렬로 숨길 수 있으므로 **기각**(성능).
- **fail-open(검사 실패 시 통과)** — 가용성은 좋으나 안전 검사가 조용히 무력화될 수 있다. 안전 검사의
  실패는 **막는 쪽**이 맞다 → **기각**.
- **post 검사 생략(pre만)** — LLM 종합 출력(ADR-0053)·워커 데이터를 탄 콘텐츠가 검사되지 않는다.
  입력만으로는 출력 안전을 보장 못 함 → **기각**(pre+post 둘 다).

## 영향
- **agents.md / operations.md** — 가드레일이 **plan과 병렬(pre) + 방출 직전(post)** 로 서는 그림.
  ADR-0052의 2-단계를 ②에 구체 배선.
- **계약** — 차단·완화 응답은 기존 §2.1 봉투/`text`로 표현(신규 계약 없음). 429 등 에지 친화 검사는
  여전히 BFF/에지와 분담(ADR-0052 부분 채택).
- **레이턴시** — pre는 병렬로 추가 지연 ≈ 0. post는 결정적 정규식으로 경미(측정은
  `verify_compose_timing.py`).
- 상세 규칙·PII 패턴·감사 로그는 `specs/trust-safety-baseline/`에서 이 배선 위에 확장(후속).

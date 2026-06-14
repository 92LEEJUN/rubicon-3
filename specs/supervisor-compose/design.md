# 설계 (Design) — 슈퍼바이저 응답 종합(Compose) + 병렬 가드레일

> `requirements.md`(요구사항 1~4)를 어떻게 만족시킬지 설계한다. 공유 모델·계약은
> [`docs/orchestration.md`](../../docs/orchestration.md)·[`docs/agents.md`](../../docs/agents.md)·
> [`docs/response-templates.md`](../../docs/response-templates.md)를 참조하고, 결정 근거는
> [ADR-0053](../../docs/adr/0053-supervisor-compose.md)·[ADR-0054](../../docs/adr/0054-guardrail-parallel.md)에 둔다.

## 개요
LLM 플래너(`LLMPlanner`)를 **슈퍼바이저**로 승격한다 — 같은 주입체가 턴의 **앞**(plan=의도 추출)과
**뒤**(compose=응답 종합)를 모두 담당한다. 가드레일(`Guardrail`)은 **결정적 규칙** 에이전트로,
의도 추출과 **병렬**로 입력을 검사(pre-screen, fail-closed)하고 방출 직전 출력을 검사(post-check)한다.
세 가지 모두 **`CapabilityOrchestrator.astream`(비동기 서빙 경로)** 에만 얹고, 동기 경로(`build_turn`/
`stream_turn`)와 `COMPOSE`/`GUARDRAIL` off는 **오늘과 동일**하다(스트랭글러).

## 아키텍처

```
사용자 메시지
   │
   ├──────────────┬───────────────┐  ✦ asyncio.gather (병렬, R2-1) ✦
   ▼              ▼
[Supervisor.plan]   [Guardrail.screen]   ← 결정적(R2-5), 예외→block(R2-3)
 intent→Plan         Verdict
   └──────┬─────────┘  join
          ▼
     verdict.allowed? ──no──► refusal 섹션(capability 스킵) → flow → done   (R2-2 fail-closed)
          │ yes
          ▼
   _run_capabilities → 섹션[]{facts, 카드/CTA}   (② 결정론, 변경 없음)
          ▼  ── BARRIER: 모든 섹션 collect (first-token 지연 비용, 승인됨) ──
   handled 섹션 ≥ 2 ? ──no──► (compose 스킵, R1-5)
          │ yes
          ▼
   [Supervisor.compose]  message + plan + facts → 내러티브(R1-1)
          │ 실패 → 내러티브 없이 원본 섹션 폴백(R1-4)
          ▼
   out = [narration(text)] + 원본 섹션(불변, R1-2)
          ▼
   [Guardrail.check]  PII 마스킹·정책(post, R3) · 예외→error 폴백(R3-2)
          ▼
   section* → flow → done   (§2.1, R4-2)
```

## 주요 컴포넌트 / 인터페이스

- **`LLMPlanner`(→ 슈퍼바이저)** — 기존 `propose`/`apropose`(plan)에 **종합 메서드 추가** _(요구사항 1)_:
  - `compose(message, plan, facts) -> str` / `acompose(...)` — facts(섹션 요약)를 받아 내러티브 1편 생성.
  - system 프롬프트 = `prompts.COMPOSER_PROMPT`(BASE_POLICY + 종합 지침). **데이터 재생성 금지**, 카드
    "참조"만, 과장·허위 금지(R1-2). 같은 모델·클라이언트(`get_client`/`achat_completion`) 재사용.
- **`Guardrail`**(신규 `orchestrator/guardrail.py`) — 결정적 규칙 에이전트 _(요구사항 2·3)_:
  - `screen(message) -> Verdict` / `ascreen(...)` — 인젝션 패턴("이전 지시 무시"·jailbreak)·남용 탐지.
  - `check(sections) -> sections` — 텍스트 메시지의 PII(전화·카드·이메일) 마스킹(R3-3, 구조 필드 불변).
  - `refusal_section(verdict) -> MessageSection` — 안전 거부(handled=False, text).
  - `Verdict(allowed, reason, topics, soften)` 데이터클래스.
- **`CapabilityOrchestrator`** — `astream`에 단계 배선 _(요구사항 1·2·3·4)_:
  - 생성자에 `guardrail=None` 주입. 토글 헬퍼 `compose_on()`/`guardrail_on()`(env, 매 호출 평가).
  - `_screen_and_route(message)` — `asyncio.gather(ascreen, aroute)`로 병렬, screen 예외→block(R2-3).
  - `_section_facts(sections)` — 섹션→{label,intent,kind,brief} 요약(compose 입력).
  - `_narration_section(text)` — intent="narration", kind="text", data={message, prose:True, composed:True}.
  - compose 가능 조건 `_can_compose()` = `llm_planner`가 `acompose` 보유.
- **`internal.py`** — `_build_cap_orch`에서 `Guardrail()` 주입(결정적, 항상 생성). compose는 `COMPOSE`
  + 플래너(LLM_BACKED) 존재 시. 토글은 오케스트레이터가 env로 평가.

## 데이터 모델
- 신규 계약 **없음** _(요구사항 4-1)_. 내러티브 = 기존 `text` 템플릿 재사용, `intent="narration"`,
  `data.prose=true`·`data.composed=true`. FE/BFF는 text 렌더러로 그대로 표시(미지 intent 무해).
- `Verdict`는 내부 타입(계약 비노출).

## 에러 처리
- **pre-screen 실패** → block(fail-closed, R2-3). 안전 거부 섹션 → flow None → done.
- **compose 실패** → 내러티브 생략, 원본 섹션 방출(R1-4, 턴 유지).
- **post-check 실패** → 미검증 내용 방출 금지 → §2.1 error 폴백(R3-2).
- **그 외 astream 전체 예외** → 기존 error 봉투(R13) 유지.

## 테스트 전략
- **단위(결정적, stub)** — `tests/test_compose.py`:
  - compose: ≥2 handled→내러티브 선두(R1-1)·구조 섹션 불변(R1-2)·off=무내러티브(R1-3)·실패 폴백(R1-4)·
    단일 섹션 스킵(R1-5). stub 플래너(`acompose`)로 LLM 없이 검증.
  - guardrail: 인젝션 입력→block+capability 스킵(R2-2)·예외→block(R2-3)·off 회귀(R2-4)·
    post PII 마스킹(R3-1·3-3)·post 예외→error(R3-2). stub/실 Guardrail 규칙.
  - 병렬 라우팅: gather 경로가 plan+verdict를 함께 반환(R2-1).
- **회귀** — 기존 `test_capability.py`(toggle off 기본)·`test_internal_*`가 그대로 green.
- **타이밍(수동)** — `verify_compose_timing.py`: compose off/on의 **총 E2E·first-token** 측정
  (실 LLM은 CI 부재 → stub 지연 시뮬레이션 + 결정적 구간). 라우팅 홉은 `verify_e2e_timing.py` 참조.

## 설계 결정 / 대안
- **플래너=슈퍼바이저(별도 Composer 워커 아님)** — 같은 두뇌가 plan 문맥을 들고 종합 → 컨텍스트 전달
  최소·plan과 정합. 대안(독립 Composer)은 plan을 다시 전달해야 하고 주입체가 하나 더 늘어 기각(ADR-0053).
- **가드레일 병렬 + fail-closed** — 직렬 지연 0, 안전은 실패 시 통과 금지(ADR-0054). 차단 시 라우팅 홉이
  낭비되나(병렬), 차단은 드물어 수용.
- **내러티브 선두 + 원본 섹션 유지(2-track 미구현)** — 카드 선-전송(2-track)으로 first-token을 회복하는
  최적화는 가능하나 섹션 순서·복잡도↑ → v1은 **배리어 후 내러티브 선두**(단순·안전, first-token 지연 감수).
  텍스트 섹션을 내러티브로 접는 최적화도 후속(데이터 필드 손실 위험 회피).
- **post-check는 텍스트만** — 계약 필드(가격·id) 훼손 방지(R3-3).

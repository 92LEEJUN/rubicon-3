# LLM 오케스트레이션 (Orchestration)

> **기반 문서 (공유).** 대화 오케스트레이터의 내부 동작 — 의도 처리·tool 호출·RAG·응답 생성 —
> 을 정의한다. 외부 API는 `docs/api-contract.md`, 데이터 타입은 `docs/data-model.md`,
> 응답 표현은 `docs/response-templates.md`, 비즈니스 로직 결정은
> `specs/samsung-ai-concierge/design.md` §6 를 본다.

## 1. 개요 / 모델

- **범용 LLM**(provider-agnostic, `architecture.md` §2). 비용/지연 균형 모델을 기본으로,
  단순·대량 처리는 경량 모델, 복잡 추론은 상위 모델로 라우팅한다.
- 호출은 단일 **LLM 채팅/메시지 API** 기반. **tool 호출(function calling)·구조화 출력·스트리밍**은
  별도 API가 아니라 이 호출의 기능으로 가정한다.
- 오케스트레이터는 **워크플로(코드가 루프 제어)** 형태. 완전 자율 에이전트가 아니라,
  의도 분류 → tool 선택/실행 → 응답 생성을 **우리 코드가 조율**한다.

## 2. 처리 파이프라인

```text
수신(user_message)
  → 1) 의도 분류·분해   (design §6.1 = 하이브리드: 구조화 출력 + 규칙 가드레일)
  → 2) 흐름 반영        (FlowState: 신규/전환/복원 — design §6.5·§6.7)
  → 3) tool 선택·실행   (LLM tool 호출; 구현은 함수/DB/Port — §3)
  → 4) 근거 보강(RAG)   (해결책 등 grounding — design §6.2 = RAG)
  → 5) 응답 생성        (Template 구조화 출력 — response-templates)
  → 6) 스트리밍 전달    (delta/template/flow/done — api-contract §2.1)
```

복합 질문(R7)은 1)에서 의도별로 분해 → 우선순위(안전/CS 먼저, design §6.6) → 순차 처리,
의도별 템플릿을 섹션으로 묶어 반환.

## 3. Tool(함수) 레이어 — API vs DB vs compute

LLM에 노출하는 **tool은 함수 시그니처**다. 구현 백엔드는 무관하며, 이것이 "전부 API가 아니다"의 실현이다.

| tool(예) | 설명 | 구현 백엔드 | 도메인 |
|----------|------|-------------|--------|
| `get_device_status` | 기기 상태·이상 조회 | **Port(API)** SmartThings | 기기(R2·R5) |
| `search_solutions` | 해결 가이드 검색(RAG) | **DB/검색** + TrustP | CS(R3) |
| `match_parts` | 기기↔부품 매칭 | **DB** 카탈로그 | 카탈로그(R4·R8) |
| `get_recommendations` | 개인화 추천 | **DB** 이력+보유기기 | 개인화(R8) |
| `get_history` | 대화·주문 이력 | **DB**(Repository) | 이력(R12) |
| `create_order` | 주문 확정 | **Port** O2O + ActionGate | 주문(R4·R17) |

- **결정 규칙** — 외부 시스템 연동이면 Port(API화), 내부 데이터면 Repository(DB), 순수 계산이면 함수.
  tool 정의는 이를 숨기고 LLM에는 동일하게 보인다.
- tool 호출 메커니즘: LLM이 tool 호출을 요청 → 우리가 실행 → 결과 회신 → 반복.
  **수동 루프**(human-in-the-loop·게이트 제어 필요)로 구현한다.
- tool description은 **언제 호출할지 명시**(트리거 조건)해 호출 정확도를 높인다.
- **되돌릴 수 없는 행동**(`create_order` 등)은 자동 실행하지 않고 `confirmation`/ActionGate 확인 후 커밋(R17).

## 4. 의도 분류·분해 (design §6.1 = 하이브리드)

- **구조화 출력**(JSON 스키마 강제)으로 분류+분해를 한 번에 받는다.
  ```python
  # 출력 스키마(의사)
  { "intents": [ { "type": "DEVICE_STATUS|TROUBLESHOOT|ORDER|RECOMMEND|GENERAL",
                   "slots": dict, "priority": int } ],
    "is_compound": bool }
  ```
- **규칙 가드레일** — 핵심 의도(주문·핸드오프 등 민감/되돌릴 수 없는 것)는 LLM 분류에만 의존하지 않고
  규칙으로 한 번 더 검증(오분류 시 피해 큰 경로 보호).

## 5. RAG 파이프라인 (design §6.2)

해결책·정보성 답변은 **근거 기반**으로 생성(R2·R3).
```text
retrieve  → CS 지식/해결가이드 검색(DB/벡터·키워드)
augment   → 검색 근거를 컨텍스트로 주입
generate  → LLM으로 답변 + 출처 표기(TrustP)
```
- 근거 부족·검색 실패 시 추측하지 않고 폴백(R13) 또는 핸드오프 유도(R18).
- MVP는 TrustP/지식 일부 실데이터 + Mock(architecture §5).

## 6. 프롬프트 구조 / 캐싱

- **system**(역할·정책·안전 규칙) → **tools**(결정적 순서) → **messages**(세션 맥락·화면 맥락·입력) 순서.
- **프롬프트 캐싱** — 안정적인 system+tools 프리픽스를 캐시해 비용·지연 절감. 휘발성(타임스탬프·세션 ID)은
  프리픽스 뒤에 둔다. (캐싱은 프리픽스 매치라 앞쪽 변경 시 전체 무효)
- **추론 깊이 조절(reasoning effort)** — 복잡 추론은 깊게, 단순 분류/조회는 얕게 해 비용·지연을 조절한다.

## 7. 스트리밍 / 세션

- 응답은 **스트리밍 우선**(R14). LLM 스트림 → 오케스트레이터가 청크를 클라이언트 계약
  (`delta`/`template`/`flow`/`done`)으로 변환·중계(architecture §9 = API/표현 계층).
- **FlowState**(진행 흐름·세션 맥락)를 1급으로 유지(design §6.7). tool 결과·인터랙션 회신을 반영해 다음 단계로.
- 서버사이드 tool 루프 한계 등으로 중단되면 재요청으로 이어간다.

## 8. 안전 / 폴백

- **되돌릴 수 없는 커밋만** LLM 경로 밖 결정적 처리 + 확인(R17, architecture §8). 대화형 CTA 회신
  (`choices` 등)은 `/chat`으로 재진입해 파이프라인(§2)을 다시 타며 **LLM을 탈 수 있다.**
  커밋 *주변*의 요약·후속 제안 생성도 LLM이 담당한다.
- 외부/LLM 실패는 부분 degradation으로 흡수, 최소 `text` 응답 보장(R13).
- LLM의 거부/안전 응답 등 예외는 폴백 처리 후 사용자에게 안전하게 안내.

## 9. 테스트 / 비범위

- tool 레이어는 Mock 구현으로 오케스트레이션 로직을 LLM 없이 단위 검증 가능.
- 실제 프롬프트 문구·평가셋·세부 튜닝은 구현 단계에서 확정(본 문서는 구조 정의).

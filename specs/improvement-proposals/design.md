# 설계 (Design) — 개선 제안 엔진 (propose-only)

> 요구사항 1~5 충족. 근거: [ADR-0067](../../docs/adr/0067-improvement-proposals-human-gated.md).
> 신호 공급 ADR-0066, 실험 ADR-0064(S8), 감사 ADR-0061/S7, 분석 R28.

## 개요
**제안만 만들고 적용은 사람**인 백오피스 엔진. 4단계(수집→제안→리뷰 큐→실험 검증)를 결정적·내부 한정으로
구현한다. **자동 적용 코드 경로를 만들지 않는다**(ADR-0067 불변 원칙 — 설계에서 그 함수가 존재하지 않음).
토글 `SELF_IMPROVE` 기본 off.

## 아키텍처
```
신호                제안                리뷰 큐               검증              적용
SignalCollector → ProposalEngine → ReviewQueue(상태기계) → ExperimentBridge → (사람·PR)
(대화결과·라우팅    (패턴→구조화        제안됨→검토중→        (S8 A/B,          ❌ 코드 경로 없음
신뢰도·전환·만족도   제안: 증거·영향·     승인|기각→검증중→     ADR-0064)         git/PR로 사람이
·실험결과)          변경후보)           적용)                                  반영·롤백
        ▲ analytics(R28)·Engagement(R29)·만족도(ADR-0066)            감사: ADR-0061/S7
```

## 주요 컴포넌트 / 인터페이스
- **`SignalCollector`** — 신호 수집·정규화 _(요구사항 1)_. 소스: 대화 결과·저신뢰 라우팅·clarify 빈발·
  템플릿 전환·만족도(ADR-0066)·실험(S8). 동의·가명화(R28) 준수. `collect(event)`·`window(period)`.
- **`ProposalEngine`** — 패턴 탐지(임계) → `Proposal` 생성 _(요구사항 2)_. 결정론 규칙(실 LLM 분석 선택).
  **수정 API 없음** — 오직 제안 산출. `analyze(signals) -> list[Proposal]`.
- **`ReviewQueue`** — 상태기계 + 영속 _(요구사항 3)_. `submit`·`review`·`approve`·`reject`·`mark_applied`.
  **적용은 사람 호출만**(시스템 자동 transition 없음). 결정·적용은 감사(ADR-0061) 기록. 기각 중복 억제.
- **`ExperimentBridge`** — 승인 제안 → S8 실험 생성/결과 첨부 _(요구사항 4)_. `to_experiment(proposal)`·
  `attach_result(proposal, experiment_result)`. 채택은 사람.
- **노출** — 운영 내부 라우터(`/internal/improve/*`: 제안 목록·리뷰·상태)로 한정 _(요구사항 5-2)_, `wiring`
  등록. 토글 off면 미등록(회귀 불변).

## 데이터 모델
- `Signal{ kind, ref, value, at, consent_ok }`
- `Proposal{ id, kind, evidence[], impact_estimate, change_candidate, status, created_at }`
  - `status: proposed | in_review | approved | rejected | validating | applied`
- `ReviewDecision{ proposal_id, actor, decision, note, at }` (감사)
- **자동 적용을 표현하는 필드/상태 없음** — `applied`는 사람이 외부(PR)에서 반영 후 수동 표기.

## 에러 처리
- 수집·분석 실패 → 비차단(루프는 운영 보조). 사용자 대면 영향 0.

## 테스트 전략
- `backend/tests/test_improvement_proposals.py` — 수집·정규화(R1)·패턴→제안 생성(R2-1)·**수정 API 부재
  단언**(R2-2: 엔진에 적용/수정 메서드가 없음을 테스트로 고정)·리뷰 상태기계·적용은 수동만(R3)·S8 연계
  (R4)·토글 off 회귀(R5). 결정적·Mock.

## 설계 결정
- **자동 적용 경로 부재를 설계로 못박음** — "수정 함수가 존재하지 않는다"를 테스트로 고정(안전의 코드화).
- **승인 ≠ 적용** — 승인 후 S8 검증, 적용은 사람이 PR로(git 추적·롤백).
- **내부 한정** — 사용자 계약 무변경(백오피스).

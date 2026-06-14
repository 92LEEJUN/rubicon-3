# 작업 (Tasks) — 개선 제안 엔진 (propose-only)

> `design.md` 구현 체크리스트. **스펙 단계 — 구현은 사용자 확인 후 시작.**

- [x] 1. ADR-0067 + 인덱스 _(요구사항 1~5)_
- [x] 2. `SignalCollector`(수집·정규화·토글/동의 게이트, `app/improve/signals.py`) + 테스트 _(요구사항 1)_
- [x] 3. `ProposalEngine`(패턴→구조화 제안, **수정 API 부재**, `proposals.py`) + 부재 단언 테스트 _(요구사항 2)_
- [x] 4. `ReviewQueue`(상태기계·적용은 수동·감사 ADR-0061·기각 중복억제, `review.py`) + 테스트 _(요구사항 3)_
- [x] 5. `ExperimentBridge`(승인→S8 실험·결과 첨부, `bridge.py`) + 테스트 _(요구사항 4)_
- [x] 6. 내부 라우터 `/internal/improve/*`(toggle off=404 inert) + `registry.py` 등록 _(요구사항 5)_
- [x] 7. 검증 — `test_improvement_proposals.py`(11)·`test_improve_router.py`(4) + 전 스위트 회귀 green·ruff

## 진행 메모
- **자동 적용 경로 없음**(ADR-0067) — 그 부재를 테스트로 고정. 승인 후 검증(S8), 적용은 사람(PR).
- 신호 입력은 ADR-0066(만족도·미해결·이탈) + analytics(R28) + 실험(S8).

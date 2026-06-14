# 작업 (Tasks) — 실험·롤아웃(Runtime A/B)

> `design.md`를 구현으로 나눈 체크리스트. 끝에 관련 요구사항 번호 표기.

## 작업 목록

- [x] 1. ADR-0064 작성 + 인덱스(README) append _(요구사항 1~6)_
- [x] 2. specs 3종(requirements/design/tasks) _(요구사항 1~6)_
- [x] 3. BE `experiments/registry.py` — Variant·Experiment·REGISTRY·get/register/default _(요구사항 2)_
- [x] 4. BE `experiments/assignment.py` — 토글·_bucket·assign·variant_for _(요구사항 1, 3, 4, 6)_
- [x] 5. BE `experiments/exposure.py` — record_exposure(append·de-dup·토글 게이트) _(요구사항 5)_
- [x] 6. BE `experiments/router.py` + `registry.py` 1줄 append(wiring.register_router) _(요구사항 4.3)_
- [x] 7. analytics 택소노미 append — `experiment_exposed` (bff KNOWN_EVENTS · FE AnalyticsEventName) _(요구사항 5.1)_
- [x] 8. FE `experiments/client.ts` — ExperimentDef·assignLocal·fetchAssignments _(요구사항 4.2, 4.3, 6)_
- [x] 9. FE `experiments/useVariant.ts` + `index.ts` — 훅·폴백·노출 track _(요구사항 4.2, 5)_
- [x] 10. 테스트 — BE `test_experiments.py`, FE `client.test.ts`·`useVariant.test.tsx` _(요구사항 1~6)_
- [x] 11. 검증 — ruff·pytest·jest·eslint 클린, commit·push _(전체)_

## 진행 메모
- contract.ts는 추가 변경 불필요(엔드포인트는 `/internal/experiments`, 내부 운영 표면 — FE 클라이언트 타입은 experiments 모듈 자체에 둠).
- exposure de-dup은 인프로세스 셋(영속 아님) — 데모/검증 범위.

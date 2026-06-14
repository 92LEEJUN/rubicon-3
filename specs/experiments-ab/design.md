# 설계 (Design) — 실험·롤아웃(Runtime A/B)

> `requirements.md`의 요구사항을 **어떻게** 만족시킬지 설명한다.
> 기반: ADR-0064. 공유 토대 참조 — 설정/토글은 [`docs/adr/0056`](../../docs/adr/0056-environment-config-baseline.md),
> 배선 시임은 [`backend/app/platform/wiring.py`](../../backend/app/platform/wiring.py)·`registry.py`,
> 분석 싱크는 [`docs/analytics.md`](../../docs/analytics.md)·`bff/gateway/analytics.py`·
> `frontend/src/analytics/track.ts`.

## 개요
실험을 **레지스트리**(키·variant·가중치·rollout·holdout)로 선언하고, **결정적 해시**로
unit_id를 variant에 sticky 분배한다. BE는 헬퍼(`variant_for`)로, FE는 훅(`useVariant`)으로
같은 규칙을 읽는다. 노출은 기존 분석 택소노미에 `experiment_exposed` 이벤트를 **append**한다.
전부 토글 `EXPERIMENTS`(기본 off) 뒤 — off면 항상 control(회귀 불변).

## 아키텍처

```
                EXPERIMENTS=off → 항상 control (회귀 불변)
                         │ on
   unit_id ── hash(key|unit) ──► bucket[0,1) ──► rollout/holdout 게이트 ──► 가중 variant
                                                         │ control(미노출)
   BE: variant_for(key, unit)  ──┐
   엔드포인트 /internal/experiments/assign ──► FE client ──► useVariant(key)
                                  └─► exposure.record() ──► analytics 싱크(experiment_exposed)
```

- **결정적 버킷**: `bucket = (md5(f"{salt}:{key}:{unit}") 상위 비트) / 2^n ∈ [0,1)`.
  stdlib `hashlib`만 사용(새 의존성 없음, 요구사항 1.1·1.2).
- BE/FE는 **동일 알고리즘**을 각 언어로 구현(FE는 djb2 류 경량 해시 — 엔드포인트로 BE 결과를
  받을 수 있어 FE 로컬 해시는 오프라인/폴백용. 계약상 권위는 BE, 요구사항 4.3).

## 주요 컴포넌트 / 인터페이스

### Backend — `backend/app/experiments/*`
- **`registry.py`** — `Experiment(key, variants=[Variant(name, weight)], control, rollout, holdout, salt)`
  데이터클래스 + 인메모리 `REGISTRY`. `get(key) -> Experiment | None`, `register(exp)`,
  `default_registry()`(예시 실험 시드). _(요구사항 2)_
- **`assignment.py`**
  - `experiments_enabled() -> bool` — `EXPERIMENTS` env 토글(기본 off). _(요구사항 3.1)_
  - `_bucket(salt, key, unit) -> float` — 결정적 [0,1). _(요구사항 1)_
  - `assign(exp, unit) -> str` — rollout/holdout 게이트 후 가중 분배, 토글 off거나 unit
    없으면 control. _(요구사항 1·6)_
  - `variant_for(key, unit, *, expose=False) -> str` — 레지스트리 조회 + assign (+옵션 노출).
    미등록 키·예외 시 control 폴백. _(요구사항 2.2·4.1)_
- **`exposure.py`** — `record_exposure(key, variant, unit, sink=...)` — 기존 분석 싱크에
  `experiment_exposed`를 append. `(unit,key,variant)` de-dup 셋. 토글 off면 no-op. _(요구사항 5)_
- **`router.py`** — `APIRouter(/internal/experiments)`:
  - `GET /assign?keys=a,b` — 헤더 신원(`resolve_principal`)으로 unit 해석, 키별 variant 맵 반환
    + 노출 기록. `wiring.register_router`로 등록(`registry.py` 1줄 append). _(요구사항 4.3)_

### Frontend — `frontend/src/experiments/*`
- **`client.ts`** — `ExperimentDef`·`assignLocal(def, unit)`(BE와 동형 경량 해시·rollout/holdout),
  `fetchAssignments(cfg, keys)`(BE `/internal/experiments/assign` 조회, 비차단 폴백). _(요구사항 4.2·4.3)_
- **`useVariant.ts`** — `useVariant(key, opts?) -> string`. 우선순위: 주입된 assignment 맵 →
  BE fetch 결과 → 로컬 def 해시 → control. 노출은 `track('experiment_exposed', {...})`로 1회 발행
  (track.ts append). 토글 off(또는 def 없음)면 control. _(요구사항 4.2·5)_
- **`index.ts`** — barrel.

### 분석 택소노미 append (기존 시그니처 불변)
- `bff/gateway/analytics.py` `KNOWN_EVENTS`에 `"experiment_exposed"` **추가만**.
- `frontend/src/analytics/track.ts` `AnalyticsEventName` 유니온에 `'experiment_exposed'` **추가만**.
- 기존 이벤트·함수 시그니처·계약 형태 불변(요구사항 5.1).

## 데이터 모델

```python
@dataclass(frozen=True)
class Variant:
    name: str
    weight: float = 1.0           # 상대 가중치(합으로 정규화)

@dataclass(frozen=True)
class Experiment:
    key: str
    variants: tuple[Variant, ...]
    control: str                  # 폴백/홀드아웃/롤아웃-외 variant 이름
    rollout: float = 1.0          # [0,1] 실험 대상 트래픽 비율(canary)
    holdout: float = 0.0          # [0,1] 실험에서 제외(control 고정)되는 비율
    salt: str = ""                # 해시 솔트(키별 독립 버킷)
```

FE 대응(`ExperimentDef`)은 같은 필드(camelCase): `key·variants[{name,weight}]·control·rollout·holdout·salt`.

exposure 이벤트(택소노미 추가): `experiment_exposed`, props `{experiment, variant, unit?}`.

## 에러 처리
- 미등록 키·할당 예외 → control 폴백(무예외, 요구사항 2.2). 분석은 비차단(실패 삼킴, 기존 track 규약).
- FE fetch 실패 → 로컬 해시 또는 control 폴백(요구사항 4.2). unit 없음 → control(요구사항 1.3).
- 가중치 합 0 또는 빈 variants → control.

## 테스트 전략
- **BE 단위**(`backend/tests/test_experiments.py`): 결정성(같은 unit 동일 결과), 분포 근사
  (대량 unit이 가중치에 비례), 토글 off=control, rollout=0 전원 control, holdout 제외,
  미등록 키 폴백, exposure append + de-dup, 통합(TestClient `/internal/experiments/assign`).
- **FE 단위**(`frontend/src/experiments/*.test.ts(x)`): `assignLocal` 결정성·rollout/holdout,
  `useVariant` 폴백·노출 track 호출(`track` 스파이), 토글 off=control.
- 검증 게이트: `ruff check backend/`·`pytest`·`jest`·`eslint`.

## 설계 결정 / 대안
- **stdlib 해시(md5) vs murmur3 라이브러리** — 새 의존성 금지 제약 → stdlib `hashlib`. 분배 균일성은
  데모/실험 토대로 충분(채택).
- **FE 권위 해시 vs BE 엔드포인트** — 계약 권위는 BE(`/assign`). FE 로컬 해시는 오프라인/mock·즉시
  렌더용 폴백. 두 경로 동형이라 일관(요구사항 4.3).
- **exposure 신규 싱크 vs 기존 analytics append** — 소유 규칙(택소노미 owner append) 준수 →
  기존 싱크에 이벤트명만 추가(중복 파이프라인 금지).

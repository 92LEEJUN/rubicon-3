# ADR-0064: 실험·롤아웃(Runtime A/B) — 결정적 sticky 할당·레지스트리·노출·canary 게이트

- **상태**: 채택
- **관련**: [`specs/experiments-ab/`](../../specs/experiments-ab/requirements.md),
  [`docs/production-readiness.md`](../production-readiness.md)(S8 스트림 ⑭ 실험·롤아웃),
  ADR-0056(환경 구성·토글·배선 시임), ADR-0057(관측성 — 분석/노출 싱크 토대),
  [`docs/analytics.md`](../analytics.md)(이벤트 택소노미 — owner append)
- **비고**: ADR-0056의 토글·`wiring.register_router`·`registry` append-only 토대 **위에** 얹는다
  (S0·S1 의존). 분석 싱크(`bff/gateway/analytics.py`·`frontend/src/analytics/track.ts`)에
  이벤트명만 **추가**(택소노미 owner append, 기존 시그니처 불변).

## 배경
MVP에는 런타임 실험·점진 롤아웃 수단이 없다(`production-readiness.md` 보강 렌즈 "실험·롤아웃" = ⬜).
프로덕션에서 기능을 안전하게 출시하려면 (1) 사용자를 variant에 **결정적·sticky**하게 분배하고,
(2) 그 분배대로 FE/BE가 분기하며, (3) **누가 무엇에 노출됐는지** 측정하고, (4) **canary/홀드아웃**
으로 위험을 통제하는 토대가 필요하다.

제약: **새 무거운 의존성 금지(stdlib/기존 React만)**, **토글 기본 off=회귀 불변(스트랭글러)**,
앱 팩토리(`internal.py`)·`production-readiness.md`·기존 분석 이벤트는 직접 편집/변경 금지.

## 결정
실험 토대를 `backend/app/experiments/*`(BE)·`frontend/src/experiments/*`(FE)에 신설하고,
토글 `EXPERIMENTS`(기본 off) 뒤에 둔다. off면 모든 할당이 **control = 기존 동작**.

- **① 실험 레지스트리** — `Experiment(key, variants=[Variant(name, weight)], control, rollout,
  holdout, salt)` 데이터클래스 + 인메모리 `REGISTRY`. 키로 조회, 미등록 키는 control 폴백(무예외).
  FE는 동형 `ExperimentDef`(camelCase). _(요구사항 2)_
- **② 결정적 sticky 할당** — `bucket(salt,key,unit) = hashlib.md5("{salt}:{key}:{unit}") 상위
  비트 / 2^n ∈ [0,1)`. 같은 unit→항상 같은 variant(sticky). 가중치 누적 구간으로 variant 선택.
  `unit_id`(user_id 또는 guest 토큰)를 신원에서 해석. stdlib only. _(요구사항 1)_
- **③ canary·홀드아웃 게이트** — `holdout` 구간 unit은 control 고정, `rollout` 비율 밖 unit은
  control(미노출). rollout=0 → 전원 control. 게이트도 결정적 버킷으로 평가(별 솔트). _(요구사항 6)_
- **④ variant 전달(FE/BE 동형)** — BE 헬퍼 `variant_for(key, unit, expose=?)`, FE 훅
  `useVariant(key)`. 계약 권위는 BE 엔드포인트 `GET /internal/experiments/assign`
  (`wiring.register_router`로 등록, `registry.py` 1줄 append). FE는 BE 결과 우선, 없으면 로컬
  동형 해시(오프라인/mock), 그래도 없으면 control. _(요구사항 4)_
- **⑤ 노출 로깅(append)** — `experiment_exposed` 이벤트를 **기존 분석 싱크**에 추가(택소노미 owner
  append). BE `exposure.record_exposure`는 BFF/인메모리 싱크에, FE 훅은 `track()`에 1회 발행.
  `(unit,key,variant)` de-dup. 토글 off면 no-op. 기존 이벤트/시그니처 불변. _(요구사항 5)_

> 본 ADR은 **구조 결정**이다. 토글 기본 off라 BE 헬퍼·FE 훅·엔드포인트는 control만 반환하고
> 노출도 발행하지 않아 동작·계약을 바꾸지 않는다(회귀 불변).

## 대안 / 기각
- **외부 실험 SaaS/SDK(LaunchDarkly·Optimizely 등) 채택** — 즉시 기능을 얻지만 새 무거운 의존성·
  공급망/비용 표면·외부 결합. **기각** — 인터페이스 동형의 인프로세스 토대로 충분(실 SaaS는 어댑터
  교체점, 범위 외).
- **murmur3 등 해시 라이브러리** — 분배 균일성↑이지만 새 의존성. **기각** — stdlib `hashlib`로 데모/
  실험 토대 충분.
- **신규 exposure 분석 파이프라인 신설** — 이벤트 이중 파이프라인·소유 규칙 위반. **기각** — 기존
  analytics 싱크에 이벤트명만 추가(택소노미 owner append).
- **앱 팩토리(internal.py)에 라우터 직접 추가** — 병렬 스트림과 공유 라인 충돌. **기각** —
  `wiring.register_router` + `registry.py` 1줄 append(ADR-0056).
- **항상 on(토글 없음)** — 회귀·동작 변경 위험. **기각** — `EXPERIMENTS` 토글 뒤(기본 off), control 폴백.

## 영향
- **production-readiness.md** — S8(실험 A/B)·보강 렌즈 "실험·롤아웃" 셀을 main이 통합 시 ⬜→✅로 갱신
  (본 ADR이 근거). 매트릭스 라인은 본 작업에서 편집하지 않는다(소유 = main 통합).
- **계약** — 외부 노출 봉투/기존 엔드포인트 **변경 없음**. 신규 내부 운영 엔드포인트
  `/internal/experiments/assign`(부가)와 분석 이벤트 `experiment_exposed`(추가)만 더한다.
  `frontend/src/types/contract.ts`는 변경 불필요(experiments 모듈 자체 타입). 분석 택소노미는
  추가형(미지 이벤트 무해) → 3계층 깨짐 없음.
- **토글 env** — `EXPERIMENTS`(실험·롤아웃, 기본 off). 신원은 ADR-0050/`MULTITENANT` 해석을 재사용.
- **후속** — 실 SaaS 어댑터·실험 결과 분석/웨어하우스·서버측 자동 롤아웃 조정은 범위 외(deferred).

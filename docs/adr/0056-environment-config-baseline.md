# ADR-0056: 환경 계층(dev/stg/prd) & 구성 토대 + 배선 시임

- **상태**: 채택
- **관련**: [`specs/environment-config/`](../../specs/environment-config/requirements.md), [`docs/production-readiness.md`](../production-readiness.md), [operations.md](../operations.md), 12-Factor(III Config·X Dev/prod parity), ADR-0020(Port/Mock 경계), ADR-0034(provider-agnostic LLM)
- **비고**: 0053~0055는 동시 진행 스트림(supervisor-compose, PR 별도)이 점유하여 본 토대는 0056을 쓴다.

## 배경
프로덕션 준비도(`docs/production-readiness.md`)를 green으로 끌어올리는 다중 스트림 작업을 **병렬**로
진행한다. 그러나 (1) 환경별(dev/stg/prd) 동작·구성·테스트가 없고(12-Factor #5·#9 미충족), (2) 여러
스트림이 앱 팩토리(`api/internal.py`)의 미들웨어·라이프사이클 같은 **공유 라인**을 동시에 편집하면
충돌이 난다. 토대(환경 구성 + 배선 시임)를 **먼저** 세워야 이후 병렬 스트림이 충돌 없이 얹힌다.

## 결정
- **중앙 설정(`backend/app/config.py`)** — `APP_ENV ∈ {dev,stg,prd}` 단일 소스. 환경별 **기본값**
  (로그 레벨·JSON·메트릭·debug)을 제공하되 **명시 env가 항상 우선**(precedence: 명시 env > 환경 기본).
  기존 `os.getenv` 사용처는 그대로(스트랭글러·회귀 불변) — 신규 코드·환경 기본 필요처만 `get_settings()`
  를 쓴다. 시크릿 값은 보관하지 않고 env로만(`OPENAI_API_KEY` 등). 미지정·오타 env → dev(안전 기본).
- **3계층 동형** — bff(`gateway/config.py`)·frontend(`src/config/`)도 동일 `APP_ENV` 규칙(FE는 Vite
  `MODE`/`VITE_APP_ENV`). 기존 `apiBase`/mock 감지(ADR-0051)는 유지.
- **배선 시임(`backend/app/platform/wiring.py`)** — 미들웨어·라이프사이클 훅을 **append-only 레지스트리**
  로 모으고 앱 팩토리는 `wiring.apply(app)` 한 번으로 적용. 병렬 스트림은 자기 모듈에서 **등록만** 하고
  공유 라인을 편집하지 않는다(충돌 회피). 현재 비어 있음 = 무동작(회귀 불변).
- **결정적·테스트 가능** — `get_settings()` 캐시 + `reload_settings()`. 환경별 테스트 가능.

## 대안 / 기각
- **기존 `os.getenv` 산재 유지** — 환경별 기본·parity·일관성이 안 생기고 새 코드마다 재구현. **기각**(토대 필요).
- **전 env 사용처를 Settings로 강제 마이그레이션** — 범위·회귀 위험 큼. **기각** — 추가형(스트랭글러)으로
  공존, 점진 채택.
- **앱 팩토리를 매 스트림이 직접 편집** — 병렬 충돌·머지 지옥. **기각** — 등록 시임으로 분리.

## 영향
- **operations.md** — 환경 계층·구성 precedence·배선 시임 추가. `production-readiness.md`가 프로그램 추적.
- **이후 스트림(관측성·회복력·보안·A/B 등)** — 모두 이 `config`/`wiring` 위에 얹는다(웨이브 1·2).
- **계약** — 추가 없음(런타임 구성). 토글 기본 off·env 미지정=dev라 회귀 불변.

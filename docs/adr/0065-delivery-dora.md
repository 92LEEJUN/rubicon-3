# ADR-0065: 딜리버리/DORA — Build/release/run 분리 · 아티팩트 버저닝 · DORA 수집 · 환경별 배포 · 컨테이너 릴리스

- **상태**: 채택
- **관련**: [`specs/delivery-dora/`](../../specs/delivery-dora/requirements.md), [`docs/production-readiness.md`](../production-readiness.md)(S9·12-Factor #4·DORA), ADR-0056(APP_ENV 환경 계층), ADR-0060(`scripts/export_openapi.py`·CI), `.github/workflows/ci.yml`
- **스트림**: S9(딜리버리/DORA) — 12-Factor #4(Build/release/run) "release 분리·아티팩트 약함" 갭과 운영 우수성(배포 자동화·DORA) 보강.

## 배경
현재 딜리버리는 `ci.yml`(테스트·린트 게이트)과 `deploy-pages.yml`(FE gh-pages)만 있다.
**빌드↔릴리스↔런 구분, 불변 아티팩트 버저닝, 환경별(dev/stg/prd) 배포 파이프라인,
DORA 4지표 관측**이 없어 12-Factor #4가 🟡, 운영 우수성이 🟡다. 이를 **추가형·토글형**으로 메운다.
기존 CI 잡 동작·앱 런타임은 불변이어야 한다(빌드·릴리스·운영 레이어만 손댄다). 새 무거운 의존성 금지.

## 결정
1. **빌드↔릴리스↔런 분리 + 버전 스탬프** — `scripts/release.py`가 git sha·빌드 날짜(UTC)·`APP_ENV`를
   담은 **불변 버전 스탬프**를 결정적으로 산출해 `build/VERSION`(사람용)·`build/version.json`(기계용)으로
   떨군다. git 메타 부재 시 `unknown` 폴백(얕은 클론·비-git 안전). 같은 빌드 아티팩트를 여러 환경 릴리스에
   재사용(릴리스 = 빌드 + 구성). stdlib만 사용.
2. **DORA 경량 수집기** — `scripts/dora.py`가 `deployment`·`failure`·`recovery` 이벤트를 **append-only
   JSONL**(`dora-metrics.jsonl`)로 적재(`record`)하고, **배포빈도·리드타임(중앙값)·변경실패율·MTTR(중앙값)**
   4지표를 집계(`report`)한다. 이벤트 0건이면 0/`null` 기본. 손상 라인은 skip. stdlib만.
3. **환경별 배포 파이프라인** — `.github/workflows/release.yml`(신규)이 `workflow_dispatch`(입력
   `environment`: dev/stg/prd) + `push tags v*`로 동작. `environment:` 키로 stg/prd에 **GitHub Environment
   보호(승인 게이트)** 를 위임하고, 릴리스마다 DORA `deployment` 이벤트를 기록한다.
4. **컨테이너 릴리스** — **멀티스테이지 `Dockerfile`**(builder→slim runtime, **비-root** `appuser`),
   `ARG`→`LABEL org.opencontainers.image.*`(git sha·버전·빌드 날짜), `docker/entrypoint.sh`(런 단계 명시),
   `docker-compose.yml`(`APP_ENV`·포트 바인딩·`/health` healthcheck), `.dockerignore`.
5. **`ci.yml` 추가형 보강** — 기존 backend/bff/frontend/lint 잡은 **불변**, `release-dry-run` 잡만 append
   (`release.py stamp`·`dora.py report`가 실제로 도는지 빠르게 검증). S7의 `security.yml`은 건드리지 않는다.

## 대안 / 기각
- **Four Keys·DORA 대시보드(BigQuery·Cloud Run)** — 무거운 클라우드 인프라. **기각**(새 의존성/인프라 금지) — JSONL 경량 수집기로 충분(관측이 목적, BI 대시보드는 비목표).
- **버전을 앱 런타임에 동적 임베드(`/health`에 노출)** — 앱 런타임 코드 동작 변경이 필요. **기각**(S9는 빌드·릴리스·운영 레이어만) — 빌드 산출 파일로만, 런타임 참조는 차후 별 스트림에서.
- **경로/태그 단일 워크플로로 모든 환경 처리(게이트 없음)** — prd 무방비 배포 위험. **기각** — GitHub Environment 보호로 승인 게이트.
- **커스텀 승인 봇/잡 레벨 수동 게이트** — 재발명. **기각** — 표준 `environment` 보호 규칙 재사용.
- **`ci.yml`을 release 워크플로로 통합** — 게이트(테스트) 책임과 릴리스 책임 혼재. **기각** — 별 워크플로로 SRP, ci는 dry-run만 append.

## 영향
- **`.github/workflows/`** — `release.yml` 신규 + `ci.yml`에 `release-dry-run` 잡 append(기존 4잡 불변). `deploy-pages.yml`·`security.yml` 불변.
- **신규 파일** — `scripts/release.py`·`scripts/dora.py`, `Dockerfile`·`.dockerignore`·`docker/entrypoint.sh`·`docker-compose.yml`, `backend/tests/test_release.py`.
- **앱 런타임** — 미변경(빌드·릴리스·운영 레이어만). 회귀 불변.
- **의존성** — 런타임 신규 의존성 0(스크립트 stdlib만). 워크플로 YAML 검증용 `pyyaml`은 개발/CI 도구일 뿐 앱 의존성 아님.
- **production-readiness** — S9·12-Factor #4 항목의 근거. 매트릭스 셀 상태는 main 머지 시 추적 문서가 갱신(이 ADR이 직접 바꾸지 않음).

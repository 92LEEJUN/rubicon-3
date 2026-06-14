# 설계 (Design) — S9 딜리버리/DORA (Build·Release·Run)

> `requirements.md` 의 요구사항을 **어떻게** 만족시킬지 설명한다.
> 기반 문서: [`docs/production-readiness.md`](../../docs/production-readiness.md)(S9·12-Factor #4),
> [`docs/adr/0065-delivery-dora.md`](../../docs/adr/0065-delivery-dora.md),
> [`backend/app/config.py`](../../backend/app/config.py)(APP_ENV 환경 계층·ADR-0056).

## 개요
딜리버리를 **빌드 → 릴리스 → 런** 세 단계로 명시 분리한다(12-Factor #4).
- **빌드**: 코드+의존성 → 불변 아티팩트(멀티스테이지 Docker 이미지 / FE 정적 번들).
- **릴리스**: 빌드 + **버전 스탬프**(git sha·날짜·env) = 추적 가능한 릴리스. 같은 빌드를 여러 환경에 재사용.
- **런**: 환경별 워크플로가 해당 릴리스를 실행/배포(스테이징 게이트).

부수적으로 **DORA 4지표**(배포빈도·리드타임·변경실패율·MTTR)를 경량 JSONL 수집기로 기록한다.
전부 **추가형**(앱 런타임·기존 CI 잡 동작 불변, stdlib만, 새 무거운 의존성 없음).

## 아키텍처

```
            [빌드]                    [릴리스]                       [런]
  code+deps ─► Docker(멀티스테이지)   release.py: VERSION/version.json   release.yml(env: dev/stg/prd)
            ─► FE 정적 번들           (git sha·date·env 스탬프)          ├─ stg/prd: 승인 게이트
                                                       │               └─ dora.py record(deployment)
                                                       ▼
                                       scripts/dora.py  ──►  dora-metrics.jsonl (append-only)
                                            └─ report ──►  4지표 집계(JSON/stdout)
```

- `scripts/release.py` — 버전 스탬프 산출(빌드↔릴리스 경계). _(요구사항 1)_
- `scripts/dora.py` — DORA 이벤트 record/report(수집·집계). _(요구사항 2)_
- `.github/workflows/release.yml` — 환경 인지 배포 + 게이트 + DORA 기록. _(요구사항 3)_
- `Dockerfile`·`docker/`·`docker-compose.yml` — 컨테이너 빌드/실행. _(요구사항 4)_
- `.github/workflows/ci.yml` — **추가형** `release-dry-run` 잡만 append(기존 잡 불변).

## 주요 컴포넌트 / 인터페이스

### `scripts/release.py` _(요구사항 1)_
- `git_meta() -> dict` — `git rev-parse`·`git show`로 sha(short/full)·커밋시각을 읽고, 실패 시 `unknown` 폴백.
- `build_stamp(env, *, sha=None, now=None) -> dict` — `{version, app_env, git_sha, git_sha_full, build_date, commit_date}` 결정적 생성(인자 주입 가능 → 테스트 결정적).
- `version_string(stamp) -> str` — 사람용 `VERSION` 한 줄(`<date>+<sha>.<env>`).
- `write(stamp, out_dir)` — `build/VERSION`(텍스트) + `build/version.json`(기계) 둘 다 기록.
- CLI: `python scripts/release.py stamp --env stg [--out build]`.

### `scripts/dora.py` _(요구사항 2)_
- `record(event, *, store, env, sha=None, ts=None, **extra)` — `event∈{deployment,failure,recovery}`을 JSONL 한 줄 append.
- `load(store) -> list[dict]` — JSONL 파싱(빈/누락 파일 → `[]`).
- `compute(events) -> dict` — 4지표:
  - **deployment_frequency**: 기간 내 deployment 수 + 일평균.
  - **lead_time_seconds(median)**: deployment의 `commit_date`→`ts` 차(있을 때).
  - **change_failure_rate**: failure 수 / deployment 수.
  - **mttr_seconds(median)**: failure→다음 recovery 간격(매칭).
- CLI: `record`(이벤트 적재) / `report`(집계 JSON/stdout).

### 워크플로 `release.yml` _(요구사항 3)_
- `on: workflow_dispatch`(입력 `environment`: dev/stg/prd) + `push: tags: ['v*']`.
- 잡 `release`: 체크아웃 → `release.py stamp` → 아티팩트 업로드 → `dora.py record deployment`.
- `environment: ${{ inputs.environment }}` 로 stg/prd에 GitHub Environment 보호(승인) 위임 — 게이트.

### Dockerfile/compose _(요구사항 4)_
- `Dockerfile`: **stage1 builder**(wheel/deps) → **stage2 runtime**(slim, 비-root `appuser`).
- `ARG GIT_SHA/VERSION/BUILD_DATE` → `LABEL org.opencontainers.image.*`.
- `docker-compose.yml`: `APP_ENV`·`PORT`(기본 8000) env, healthcheck = `/health`.
- `docker/entrypoint.sh`: env 출력 후 uvicorn 기동(런 단계 명시).

## 데이터 모델
- **version.json**: `{version, app_env, git_sha, git_sha_full, build_date, commit_date}`.
- **dora-metrics.jsonl**(1줄=1이벤트): `{event, ts, app_env, git_sha, ...extra}`.
- **report 산출**: `{window, deployment_frequency, lead_time_seconds, change_failure_rate, mttr_seconds, counts}`.

## 에러 처리
- git 부재/얕은 클론 → `unknown` 폴백(요구사항 1-3). 스크립트는 비-0 종료 없이 진행.
- DORA 이벤트 0건 → 0/`null` 기본(요구사항 2-3). 손상 JSONL 라인은 skip(견고).
- 워크플로는 **추가형** — `security.yml`(S7)·기존 잡 미편집(요구사항 3-4).

## 테스트 전략
- `backend/tests/test_release.py`(루트 `scripts/`를 import) — 단위 테스트:
  - 버전 스탬프 결정성·폴백(요구사항 1).
  - DORA record→load round-trip, compute 4지표(빈/정상), CFR·MTTR 매칭(요구사항 2).
- 워크플로 YAML 문법: `python -c "import yaml; yaml.safe_load(...)"`(수동/CI dry-run).
- 스크립트 실제 실행: `release.py stamp`·`dora.py report` 산출 확인.

## 설계 결정 / 대안
- **경량 자체 수집기(JSONL)** vs DORA 대시보드(Four Keys·BigQuery): 무거운 인프라 → **기각**. 과제 제약(새 의존성 금지)에 stdlib JSONL이 충분.
- **버전 스탬프 파일** vs 동적 빌드 임베드: 앱 런타임 코드 동작 변경 금지 → 빌드 산출물 파일로만(런타임 미참조). 향후 `/health`가 읽도록 확장 가능(이번 범위 밖).
- **GitHub Environment 보호** vs 커스텀 승인 로직: 표준 기능 재사용(게이트). 워크플로는 환경만 선언, 보호 규칙은 레포 설정 측.
- **`release.py`/`dora.py` 분리** vs 단일 스크립트: 빌드↔릴리스 경계와 DORA 관측 책임 분리(SRP).

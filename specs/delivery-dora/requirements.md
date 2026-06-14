# 요구사항 (Requirements) — S9 딜리버리/DORA (Build·Release·Run)

## 개요
12-Factor #4(Build/release/run)의 갭을 메운다. 현재 CI(`ci.yml`)·gh-pages 배포는 있으나
**빌드↔릴리스↔런 구분, 아티팩트 버저닝, 환경별 배포 파이프라인, DORA 메트릭 수집**이 약하다.
이를 **추가형·토글형**으로 보강한다. 기존 CI 잡 동작·앱 런타임은 불변이어야 한다(빌드·릴리스·운영
레이어만 손댄다).

## 요구사항 목록

### 요구사항 1: 빌드↔릴리스↔런 분리 + 아티팩트 버저닝

**User Story:**
릴리스 담당자로서, 불변(immutable)한 버전 스탬프가 박힌 릴리스 아티팩트를 원한다,
그래서 어떤 커밋이 어떤 환경에 배포됐는지 추적·재현할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 릴리스 스크립트를 실행하면 THEN 시스템은 git sha·빌드 날짜(UTC)·환경을 담은 **버전 스탬프**(JSON 1개)를 결정적으로 산출해야 한다 (SHALL).
2. WHEN 버전 스탬프를 만들면 THEN 시스템은 `VERSION` 텍스트(사람용)와 JSON(기계용)을 모두 떨궈야 한다 (SHALL).
3. IF git 메타데이터를 읽을 수 없으면(얕은 체크아웃·비-git) THEN 시스템은 실패하지 않고 안전한 폴백 값(`unknown`)을 써야 한다 (SHALL).
4. WHEN 릴리스 단계가 끝나면 THEN 빌드(코드→아티팩트)·릴리스(아티팩트+구성=버전)·런(실행)이 **개념적으로 분리**되어, 같은 빌드를 여러 환경 릴리스에 재사용할 수 있어야 한다 (SHALL).

### 요구사항 2: DORA 메트릭 수집(경량)

**User Story:**
운영자로서, 배포빈도·리드타임·변경실패율·MTTR(4대 DORA 지표)을 기록하는 경량 수집기를 원한다,
그래서 무거운 인프라 없이 딜리버리 성능을 관측할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 워크플로/CLI가 `deployment`·`failure`·`recovery` 이벤트를 기록하면 THEN 시스템은 이를 **append-only 파일(JSONL)** 에 한 줄씩 적재해야 한다 (SHALL).
2. WHEN 적재된 이벤트로 집계를 요청하면 THEN 시스템은 **배포빈도·리드타임(중앙값)·변경실패율·MTTR(중앙값)** 4지표를 계산해 산출(파일/표준출력)해야 한다 (SHALL).
3. IF 이벤트가 없으면 THEN 시스템은 실패 없이 0/`null` 기본값을 반환해야 한다 (SHALL).
4. WHILE 수집기가 동작하는 동안 시스템은 **새 무거운 의존성 없이** stdlib만 사용해야 한다 (SHALL).

### 요구사항 3: 환경별 배포 파이프라인(APP_ENV 인지 + 스테이징 게이트)

**User Story:**
릴리스 담당자로서, dev/stg/prd를 인지하고 스테이징 게이트(수동 승인)를 거치는 배포 워크플로를 원한다,
그래서 환경 parity를 지키며 안전하게 승급(promote)할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 릴리스 워크플로를 디스패치하면 THEN 시스템은 대상 **환경(dev/stg/prd)** 을 입력으로 받아야 한다 (SHALL).
2. IF 대상이 prd면 THEN 시스템은 **승인 게이트(environment protection)** 를 거치도록 잡을 구성해야 한다 (SHALL).
3. WHEN 어떤 환경으로 릴리스하면 THEN 시스템은 해당 릴리스의 DORA `deployment` 이벤트를 기록해야 한다 (SHALL).
4. WHILE 새 워크플로가 추가돼도 시스템은 기존 `ci.yml`·`deploy-pages.yml`·`security.yml`의 동작을 바꾸지 않아야 한다 (SHALL).

### 요구사항 4: 컨테이너 릴리스(멀티스테이지 Dockerfile + 버전 라벨)

**User Story:**
플랫폼 담당자로서, 멀티스테이지로 슬림하게 빌드되고 OCI 버전 라벨이 박힌 컨테이너 이미지를 원한다,
그래서 런타임 아티팩트를 환경 간 일관되게 운반할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN backend 이미지를 빌드하면 THEN 시스템은 **멀티스테이지**(빌드 의존성 분리)로 런타임 슬림 이미지를 만들어야 한다 (SHALL).
2. WHEN 이미지를 빌드하면 THEN 시스템은 git sha·버전·빌드 날짜를 **OCI 라벨(`org.opencontainers.image.*`)** 로 박을 수 있어야 한다 (SHALL).
3. WHEN 컨테이너를 실행하면 THEN 시스템은 비-root 사용자로 uvicorn을 기동해야 한다 (SHALL).
4. WHEN 로컬 구성을 원하면 THEN 시스템은 `docker-compose`로 `APP_ENV`·포트 바인딩을 인지해 띄울 수 있어야 한다 (SHALL).

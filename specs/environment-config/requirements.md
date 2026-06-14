# 요구사항 (Requirements) — 환경 계층(dev/stg/prd) & 구성 토대

## 개요
프로덕션 준비도(`docs/production-readiness.md`)를 green으로 끌어올리는 다중 스트림 병렬 작업의
**토대**다. 환경별(dev/stg/prd) 동작·구성·테스트를 단일 소스로 세우고(12-Factor #5·#9), 이후 병렬
스트림이 앱 팩토리 공유 라인을 충돌 없이 얹도록 **배선 시임**을 제공한다. 기존 동작은 불변(스트랭글러).

## 요구사항 목록

### 요구사항 1: 환경 단일 소스 + precedence
**User Story:** 운영자로서, dev/stg/prd마다 다른 동작·구성을 한 곳에서 결정하기를 원한다, 그래서
환경 parity와 일관성을 확보할 수 있다.

**수용기준:**
1. WHEN `APP_ENV`가 dev|stg|prd 중 하나일 때 THEN 시스템은 해당 환경의 **기본값**(로그 레벨·JSON·메트릭·
   debug)을 적용해야 한다 (SHALL).
2. IF 명시 env 변수(예: `LOG_LEVEL`)가 있으면 THEN 시스템은 **환경 기본값보다 그것을 우선**해야 한다 (SHALL).
3. IF `APP_ENV`가 미지정·미지값이면 THEN 시스템은 **dev로 폴백**해야 한다 (SHALL, 안전 기본).
4. WHEN 시크릿(키 등)은 설정 객체에 **보관하지 않고 env로만** 읽어야 한다 (SHALL).

### 요구사항 2: 3계층 동형
**User Story:** 통합 담당자로서, FE/BFF/BE가 같은 환경 규칙을 따르기를 원한다.

**수용기준:**
1. WHEN BE·BFF·FE 모두 `APP_ENV`(FE는 Vite `MODE`/`VITE_APP_ENV`) 규칙을 따라야 한다 (SHALL).
2. WHILE 기존 `apiBase`/mock 감지(ADR-0051)·기존 `os.getenv` 사용처는 **불변**이어야 한다 (SHALL, 회귀).

### 요구사항 3: 배선 시임(병렬 충돌 회피)
**User Story:** 개발자로서, 여러 스트림이 앱 팩토리를 동시에 고쳐도 충돌하지 않기를 원한다.

**수용기준:**
1. WHEN 스트림은 미들웨어·라이프사이클 훅을 **레지스트리에 등록**하고, 앱은 `wiring.apply(app)`로 일괄
   적용해야 한다 (SHALL).
2. IF 등록된 항목이 없으면 THEN `apply`는 **무동작**이어야 한다 (SHALL, 회귀 불변).

### 요구사항 4: 결정적·테스트 가능
**수용기준:**
1. WHEN `get_settings()`는 캐시되고, `reload_settings()`로 갱신 가능해야 한다 (SHALL).
2. WHEN 환경별 기본·precedence·폴백은 LLM/네트워크 없이 단위 검증 가능해야 한다 (SHALL).

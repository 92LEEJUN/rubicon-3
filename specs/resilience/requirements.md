# 요구사항 (Requirements) — 신뢰성/회복력(Resilience)

## 개요
프로덕션 준비도(`docs/production-readiness.md`) S2 스트림 — Well-Architected **신뢰성** 기둥과
12-Factor **#7 Disposability**를 충족한다. 실패·과부하 상황에서 시스템이 빠르게 실패하고(서킷브레이커),
단계별 시한을 두며(타임아웃), 깨끗하게 종료되고(graceful shutdown), 부분 기능만으로도 버티며(degraded
모드), 일시 오류를 일관되게 재시도한다(공용 백오프). 모든 유틸은 **결정적·단위 테스트 가능**하고, 토글
**기본 off = 회귀 불변**(스트랭글러)이다. 새 pip 의존성 없이 stdlib·asyncio만 쓴다.

## 요구사항 목록

### 요구사항 1: 서킷브레이커
**User Story:** 운영자로서, 다운스트림(LLM·외부 서비스)이 연속 실패할 때 호출을 빠르게 차단하기를
원한다, 그래서 장애가 전파·증폭되지 않고 빠르게 실패해 회복 여지를 확보할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 연속 실패 수가 임계치(`failure_threshold`)에 도달하면 THEN 시스템은 상태를 **open**으로 전환하고
   이후 호출을 즉시 거부(`CircuitOpenError`)해야 한다 (SHALL).
2. WHILE open 상태에서 복구 시간(`recovery_timeout`)이 지나면 THEN 시스템은 **half-open**으로 전환해
   시험 호출을 1회 허용해야 한다 (SHALL).
3. IF half-open의 시험 호출이 성공하면 THEN 시스템은 **closed**로 복귀(카운터 리셋)해야 하고, 실패하면
   다시 **open**으로 돌아가야 한다 (SHALL).
4. WHEN closed 상태에서 호출이 성공하면 THEN 연속 실패 카운터를 0으로 리셋해야 한다 (SHALL).
5. WHEN 시간 경과 판정은 주입 가능한 **단조 시계(clock)** 로 결정적으로 검증 가능해야 한다 (SHALL).

### 요구사항 2: 단계별 타임아웃(ADR-0018 개념 되살림)
**User Story:** 개발자로서, 글로벌 단일 타임아웃 대신 **단계별** 시한을 두기를 원한다, 그래서 한 단계가
늘어져 전체를 막지 않고 부분 폴백으로 진행할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 단계 코루틴이 주어진 `timeout`을 초과하면 THEN 시스템은 이를 취소하고 `StageTimeout`을
   발생시켜야 한다 (SHALL).
2. IF `fallback`이 주어지면 THEN 타임아웃 시 예외 대신 **폴백 값**을 반환해야 한다 (SHALL, 부분 폴백).
3. WHEN `timeout`이 None·0 이하이면 THEN **시한 없이** 그대로 실행해야 한다 (SHALL, 회귀 불변).

### 요구사항 3: Graceful shutdown 훅
**User Story:** 운영자로서, 프로세스 종료 시 진행 중 작업을 정리하고 등록된 정리 콜백을 순서대로
실행하기를 원한다, 그래서 무중단 배포·재시작에서 상태 손상·연결 누수가 없도록 한다(Disposability).

**수용기준 (Acceptance Criteria):**
1. WHEN 정리 콜백을 등록하면 THEN shutdown 시 **역순(LIFO)** 으로 실행해야 한다 (SHALL).
2. IF 한 콜백이 예외를 던지면 THEN 나머지 콜백 실행을 **멈추지 않고** 계속해야 한다 (SHALL, best-effort).
3. WHEN 동기·비동기(코루틴) 콜백을 **모두** 지원해야 한다 (SHALL).
4. WHEN 본 모듈은 `wiring.register_shutdown`으로 graceful 종료 훅을 **등록만** 하고 앱 팩토리를
   직접 편집하지 않아야 한다 (SHALL, ADR-0056 배선 시임).

### 요구사항 4: Degraded / 부분 폴백 모드 플래그
**User Story:** 운영자로서, 일부 기능을 의도적으로 끄고(또는 자동 강등) 핵심만 제공하기를 원한다,
그래서 부분 장애에서도 서비스를 유지할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN degraded 모드 플래그를 조회·설정할 수 있어야 하며, **기본은 off**(정상)여야 한다 (SHALL, 회귀 불변).
2. IF 특정 기능(`feature`)이 degraded로 표시되면 THEN 해당 기능은 비활성으로 간주되어야 한다 (SHALL).
3. WHEN env(`RESILIENCE_DEGRADED`)로 초기 degraded 기능 집합을 줄 수 있어야 한다 (SHALL).

### 요구사항 5: 재시도/백오프 공용 유틸
**User Story:** 개발자로서, 지수 백오프+지터 재시도를 한 곳에서 일반화하기를 원한다, 그래서 `llm.py`와
중복 없이 임의의 호출에 일관되게 적용할 수 있다.

**수용기준 (Acceptance Criteria):**
1. WHEN 일시적(transient) 예외에 대해 지수 백오프+지터로 N회 재시도하고, 모두 실패하면 마지막 예외를
   재던져야 한다 (SHALL).
2. IF 비대상 예외가 발생하면 THEN **재시도하지 않고** 즉시 전파해야 한다 (SHALL).
3. WHEN 슬립 함수·지터·시계는 주입 가능해 **결정적으로 단위 검증** 가능해야 한다 (SHALL).
4. WHEN 동기·비동기 두 변형을 제공해야 한다 (SHALL).

### 요구사항 6: 결정적·회귀 불변
**수용기준 (Acceptance Criteria):**
1. WHEN 모든 유틸은 LLM·네트워크·실시간 sleep 없이 단위 검증 가능해야 한다 (SHALL).
2. WHEN 본 스트림은 `backend/app/resilience.py`(신규) + `registry.py` import 한 줄만 추가하고, 기존
   동작은 토글 off에서 불변이어야 한다 (SHALL, ADR-0056).

# ADR-0058: 신뢰성/회복력 유틸 — 서킷브레이커·단계 타임아웃·graceful shutdown·degraded·공용 백오프

- **상태**: 채택
- **관련**: [`specs/resilience/`](../../specs/resilience/requirements.md), [`docs/production-readiness.md`](../production-readiness.md)(S2), ADR-0056(config·wiring 토대), ADR-0018(단계 타임아웃·부분 폴백 — **보류 해제**), `backend/app/llm.py`(기존 백오프 패턴), Well-Architected(신뢰성), 12-Factor(VII Disposability)

## 배경
MVP에는 graceful shutdown·서킷브레이커가 없다(`production-readiness.md`: #7 ⬜, 신뢰성 갭). 실패·과부하
시 장애가 전파·증폭되고, 종료 시 진행 작업·연결이 누수된다. ADR-0018은 단계 타임아웃·부분 폴백을
"즉시 체감 작음"으로 **보류**했으나, 프로덕션 준비도 프로그램(S2)에서 신뢰성 기둥을 green으로 올리며
그 개념을 되살린다. 백오프 재시도는 `llm.py`에 패턴이 있으나 LLM 전용이라 일반화가 없다.

## 결정
`backend/app/resilience.py`(신규) 단일 모듈에 **결정적·테스트 가능**한 5개 유틸을 둔다(stdlib·asyncio만,
새 의존성 없음).

1. **서킷브레이커** — `CircuitBreaker`(closed/open/half-open). 연속 실패 임계→open, 복구 시간 경과→
   half-open 시험 1회→성공이면 closed·실패면 open. 시계(`clock`) 주입으로 결정적. open 시
   `CircuitOpenError`. 동기·비동기(`call`/`acall`).
2. **단계 타임아웃(ADR-0018 되살림)** — `run_stage(coro_factory, timeout, fallback=...)`. 글로벌 1개가
   아니라 **호출(단계) 단위** 시한. 타임아웃 시 `StageTimeout` 또는 **부분 폴백** 반환. `timeout=None`은
   바이패스(회귀 불변).
3. **graceful shutdown 훅** — `ShutdownManager`(LIFO·best-effort, sync+async). 전역 `SHUTDOWN`·
   `on_shutdown(fn)`. 토글 `RESILIENCE_ENABLED`(기본 off)가 켜질 때만 `wiring.register_shutdown`으로
   앱 종료 훅을 **등록**(앱 팩토리 직접 편집 안 함 — ADR-0056 배선 시임).
4. **degraded/부분 폴백 플래그** — `DegradedMode`(기능별 강등 집합), 전역 `DEGRADED`. env
   `RESILIENCE_DEGRADED`(콤마구분)로 초기화. 기본 비어 있음=정상.
5. **공용 재시도/백오프** — `retry`/`aretry`(지수 백오프+지터, transient 튜플 외 즉시 전파, sleep·jitter·
   시계 주입). `llm.py`의 알고리즘을 일반화하되 `llm.py`는 손대지 않는다(소유 밖). 중복 신설 금지.

**토글 기본 off = 회귀 불변.** 모듈 import는 부수효과 없음(유틸은 명시적으로 인스턴스화). 종료 훅 등록만
env 게이트라, off에서 wiring에 아무것도 등록되지 않아 기존 동작과 동일하다.

## 대안 / 기각
- **외부 라이브러리(pybreaker·tenacity·circuitbreaker)** — 새 pip 의존성 금지·범위 과대. **기각**(stdlib로 충분).
- **글로벌 단일 타임아웃** — 한 단계 지연이 전체를 막음. **기각** — ADR-0018대로 단계별.
- **`llm.py`를 직접 리팩터해 공유** — 소유 경계(S6) 침범·회귀 위험. **기각** — 일반화 유틸 신설, llm.py 불변.
- **shutdown을 앱 팩토리에서 직접 등록** — 병렬 충돌. **기각** — ADR-0056 wiring 시임으로 등록만.

## 영향
- **production-readiness.md** — #7 Disposability·신뢰성 기둥 진척(인덱스 갱신은 main 소유, 본 PR은 미편집).
- **배선** — `registry.py`에 import 1줄 append(부수효과=등록). `internal.py`·`wiring.py` 라인 불변.
- **이후 스트림** — S6(비용·캐싱)은 `retry`/서킷을 LLM 경로에 적용 가능(본 ADR은 유틸만 제공, 적용은 별건).
- **토글명** — `RESILIENCE_ENABLED`(shutdown 훅 등록), `RESILIENCE_DEGRADED`(초기 강등 집합). 기본 off.

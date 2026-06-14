# 설계 (Design) — 컴패니언·리텐션

> 요구사항 1~4 충족. 근거: [ADR-0066](../../docs/adr/0066-companion-retention.md). 게이트는 ADR-0042,
> Engagement 도메인은 ADR-0029/R29, 동의는 ADR-0030.

## 개요
컴패니언·리텐션을 **결정적 도메인 로직**(트리거·게이트·기록)으로 두고, 문구만 정책 범위 내(llm-policy)
에서 채운다. 토글 `COMPANION` 기본 off. 외부 푸시 채널은 비범위(인앱 제안까지). 모든 신호는 Engagement에
기록해 개인화·중복 방지·자기개선(ADR-0067)에 재사용한다.

## 구현 현황(재사용 vs 신규)
요구사항 1·2의 토대는 **이미 `specs/always-present-companion/`에 구현**돼 있다 — 본 라운드는 이를
**재사용**하고 **만족도 수집(요구사항 3)** 과 **자기개선 신호 연결(ADR-0067)** 만 신규로 더한다.

## 주요 컴포넌트 / 인터페이스
- **`CompanionService` / `InMemoryOpenLoopRepository`** _(요구사항 1, 기구현)_ — open-loop 멱등 기록·
  `resolve_loop`·`dismiss_loop`·`last_touch`(`app/companion.py`·`app/repositories/open_loop.py`).
- **`ReEngagementService`** _(요구사항 2, 기구현)_ — ADR-0042 게이트 순서(① 동의/opt-in → ② cooldown(R26)
  → ③ Engagement 중복 → ④ 묶음(R27))로 후보 1건만(`candidate`/`mark_sent`, `app/reengagement.py`).
- **`SatisfactionService`** _(요구사항 3, **신규** `app/satisfaction.py`)_ — `collect(user, topic, score,
  kind, resolved)`. 미해결이면 `next_action="rediagnose"`. Engagement에 `sat:<topic>` 기록. 동의 scope
  인지로 `Signal(kind="satisfaction"|"handoff")`를 주입된 `signal_sink`(개선 엔진 COLLECTOR)로 emit.
- **엔드포인트** _(신규)_ — `POST /internal/satisfaction`(기존 companion 엔드포인트와 동거, `api/internal.py`).
- **Engagement 연계** — Engagement 도메인(R29)에 기록(중복·개인화 재사용) _(요구사항 4-2)_.
- **토글** — 기존 companion/재관여는 **consent-gated**(글로벌 토글 아님). 만족도는 **추가형**(신규 경로,
  기존 동작 불변). 신호 emit만 `SELF_IMPROVE` 게이트(ADR-0067) _(요구사항 4-1)_.

## 데이터 모델
- `OpenLoop{ id, user_id, topic, opened_at, expires_at, status: open|resolved|expired }`
- `ReengagementProposal{ trigger, topic, priority, payload }` (내부; 노출 시 기존 template로 변환)
- `Satisfaction{ user_id, turn_ref, score, comment?, resolved: bool }`
- 신규 응답 계약 최소화 — 후속/재관여는 `text`·`choices` 재사용, 만족도는 `choices`(점수)·`text`.

## 에러 처리
- 게이트/제안 실패 → 제안 생략(침묵), 턴 정상(회귀 불변).
- 만족도 수집 실패 → 비차단(수집은 선택).

## 테스트 전략
- `backend/tests/test_companion_retention.py` — open-loop 기록/만료/닫기(R1)·게이트 통과/억제(R2, 빈도·동의)·
  만족도 수집→신호 emit(R3)·토글 off 회귀(R4). 결정적(주입 시계·Mock).

## 설계 결정
- **게이트가 1순위** — 재관여 가치는 "남발 안 함"에서 나온다(P1 알림 피로). ADR-0042 재사용.
- **채널 비범위** — 인앱 제안까지. 실 푸시(roadmap F)는 후속 인프라.
- **신호는 Engagement** — analytics와 분리(ADR-0029) 유지, 자기개선 입력으로 공급.

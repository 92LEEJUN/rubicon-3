# 설계 (Design) — 컴패니언·리텐션

> 요구사항 1~4 충족. 근거: [ADR-0066](../../docs/adr/0066-companion-retention.md). 게이트는 ADR-0042,
> Engagement 도메인은 ADR-0029/R29, 동의는 ADR-0030.

## 개요
컴패니언·리텐션을 **결정적 도메인 로직**(트리거·게이트·기록)으로 두고, 문구만 정책 범위 내(llm-policy)
에서 채운다. 토글 `COMPANION` 기본 off. 외부 푸시 채널은 비범위(인앱 제안까지). 모든 신호는 Engagement에
기록해 개인화·중복 방지·자기개선(ADR-0067)에 재사용한다.

## 주요 컴포넌트 / 인터페이스
- **`OpenLoopStore`** — 미해결 스레드 기록/조회/만료/닫기 _(요구사항 1)_. 키: user_id(+thread). 인메모리/
  Mock(영속은 백킹서비스 Port, ADR-0059 재사용 가능). `record(loop)`·`pending(user)`·`close(id)`·`expire()`.
- **`ReengagementProposer`** — 트리거 평가 → 제안 생성 _(요구사항 2-1)_. 트리거: 소모품 임박·미해결·점검
  주기·재주문 주기. 출력은 **제안 후보**(노출 아님).
- **`ReengagementGate`** — ADR-0042 게이트 _(요구사항 2-2·2-3)_: 빈도 상한·중요도 임계·동의 scope(R30)
  검사 → 통과분만 표면화. 결정적·단위 검증.
- **`SatisfactionCollector`** — 해결 확인(R25)에 CSAT/NPS 인라인 수집 _(요구사항 3)_. 미해결→재진단/핸드오프.
  수집 결과를 `ImprovementSignals`(ADR-0067)로 emit.
- **Engagement 연계** — 위 결과를 Engagement 도메인(R29)에 기록(중복 제시 방지·개인화 재사용) _(요구사항 4-2)_.
- **배선** — capability/companion 경로(기존 companion 0042 위) 또는 라우터로. 토글 off면 미등록(회귀 불변).

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

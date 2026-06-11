# 사용 분석 / 이벤트 택소노미 (Analytics)

> **기반 문서 (공유).** FE↔BE가 같은 이벤트명을 쓰도록 하는 **분석 이벤트 계약**(R28).
> 타입은 `docs/data-model.md`(`AnalyticsEvent`·`AnalyticsPort`), 파이프라인은
> `docs/architecture.md` §11, 시나리오는 `specs/mvp-concierge/scenarios/`.
> 이벤트명/스키마가 바뀌면 **이 문서를 갱신**한다(FE/BE 동시 영향).

## 1. 목표 ↔ 데이터

| 알고 싶은 것 | 기법 | 소스 이벤트 |
|--------------|------|-------------|
| **어디서 이탈?** | 퍼널 | `flow_start/step/complete/abandon` (FlowState 전이) |
| **어떤 버튼으로 구매?** | 전환 기여 | `cta_click` → `order_confirmed` (`correlation_id`) |
| **어디서 머무름?** | 체류·인게이지먼트 | `screen_view`/`screen_exit`(dwell), `template_shown` |

## 2. 공통 스키마 (`AnalyticsEvent`)

```python
{ "name": str,                 # 택소노미 이벤트명 (§4)
  "ts": datetime,              # UTC
  "session_id": Id,
  "user_ref": str | None,      # 가명화 식별자 (원본 아님, R19)
  "props": dict,               # 이벤트별 속성
  "context": {                 # 공통 맥락
    "screen": str,             # 발생 화면 (S1/S2/S3 …)
    "flow": str | None,        # 진행 흐름 (troubleshoot/order …)
    "flow_step": str | None,
    "correlation_id": Id | None # 기여 추적(대화→주문 연결)
  } }
```

규칙: **모든 이벤트는 동의(`Consent.scopes`에 `analytics`)가 있을 때만** 전송. 식별자는 가명화. 비차단.

## 3. 퍼널 정의 (메인 저니)

이탈 측정용 표준 퍼널. 각 단계는 `flow_step`으로 매핑된다.

```
선제 알림 노출 → 채팅 진입 → 진단 → 해결 가이드 → 부품 제시
  → [장바구니] → 결제 확인(R17) → 주문 완료 → (사후 확인 R25)
```
- 각 단계 전이에 `flow_step` 변경 → 단계별 진입/완료율·**drop-off** 산출.
- `flow_abandon`: 흐름 미완료 종료(이탈 지점 = 마지막 `flow_step`).

**브릿지 퍼널** — `card_tap → bridge_view → (bridge_cta_click | bridge_escalate | bridge_dismiss)`.
`bridge_dismiss`는 **간단 정보로 충분**(긍정 신호), `bridge_escalate`는 대화가 필요했던 비율 → 브릿지/패널 분기 기준 튜닝에 사용.
`card_type` 값은 `response-templates.md` §9 카드 타입과 동일: `device_status`·`anomaly`·`recommendation`·`order`·`booking`·`warranty`·`notice`·`shortcut`.

## 4. 이벤트 카탈로그

| 이벤트 | 발생(주체) | 주요 props | 용도 |
|--------|-----------|-----------|------|
| `screen_view` | FE | `screen` | 체류·진입 |
| `screen_exit` | FE | `screen`, `dwell_ms` | **체류 시간** |
| `chat_open` | FE | `entry`(home/cs/fab) | 진입 분석 |
| `card_tap` | FE | `card_type` | 브릿지 퍼널 진입(R9) |
| `bridge_view` | FE | `card_type`, `dwell_ms` | 브릿지 노출·체류 |
| `bridge_cta_click` | FE | `cta`, `correlation_id` | 브릿지에서 즉시 행동 |
| `bridge_escalate` | FE | `correlation_id` | 브릿지→AI 패널 전환(P→R) |
| `bridge_dismiss` | FE | `card_type` | 브릿지로 충분(이탈 아님) |
| `message_sent` | FE | `modality`(text/image) | 인게이지먼트 |
| `template_shown` | FE | `kind` | 어떤 템플릿이 노출 |
| `cta_impression` | FE | `cta`, `template` | CTA 노출(기여 분모) |
| `cta_click` | FE | `cta`, `template`, `correlation_id` | **구매 기여 시작** |
| `flow_start` | BE/FE | `flow` | 퍼널 진입 |
| `flow_step` | BE/FE | `flow`, `step` | 퍼널 단계 |
| `flow_complete` | BE/FE | `flow` | 퍼널 완료 |
| `flow_abandon` | BE/FE | `flow`, `last_step` | **이탈 지점** |
| `add_to_cart` | BE | `part_id` | 주문 퍼널 |
| `checkout_shown` | FE | `correlation_id` | 결제 확인 노출(R17) |
| `order_confirmed` | BE | `order_id`, `correlation_id` | **전환(구매)** |
| `order_cancelled` | BE | `order_id` | 취소율(R21) |
| `notification_delivered` | BE | `type`, `priority` | 선제 도달(R20·R26) |
| `notification_opened` | FE | `type` | **선제 효과** |
| `notification_dismissed` | FE | `type` | 알림 피로 신호 |
| `handoff_started` | BE | `type`(agent/visit) | 핸드오프율(R18) |
| `resolution_confirmed` | FE | `resolved`(bool) | 해결률(R25) |

> 이벤트는 **추가만**(제거/의미 변경 금지) — 과거 데이터 호환(data-model §2 enum 규칙과 동일 철학).

## 5. 전환 기여 (Attribution)

- `cta_click`에서 `correlation_id`를 발급 → 이후 `checkout_shown`·`order_confirmed`까지 **동일 ID 전파**.
- 분석 시: `order_confirmed`를 유발한 **마지막 `cta_click`의 `cta`/`template`** 으로 기여(last-touch).
- 분모는 `cta_impression`(노출) → CTA별 클릭률·전환율 산출.

## 6. 프라이버시 / 동의 (R19)

- `Consent.scopes`에 **`analytics` 미포함이면 수집 안 함**. opt-out 시 즉시 중단.
- `user_ref`는 **가명화**(원본 식별자·연락처·결제정보 금지). `props`에 민감정보 금지.
- 삭제 요청 시 분석 데이터도 cascade 대상(R19, `ConsentPort.delete_data`).

## 7. 수집 / 전송

- **FE** — 화면·CTA·dwell 이벤트를 모아 **배치 전송**(`AnalyticsPort.track_batch`). 네트워크 실패는 무시/재시도(비차단).
- **BE** — 서버 확정 이벤트(`order_confirmed`·`notification_*`)는 직접 emit.
- **MVP** — `MockAnalyticsPort`(로컬 로그). **실** — 분석 플랫폼/웨어하우스(`architecture.md` §11).

## 8. 비범위 (후속)

- 실시간 대시보드·세션 리플레이·히트맵, A/B 테스트 프레임워크.
- 서버 웨어하우스 스키마·ETL은 실 연동 시 확정.

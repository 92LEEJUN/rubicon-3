# 사용 분석 / 이벤트 택소노미 (Analytics)

> **상태: 계약만 정의 · 미배선(deferred).** `AnalyticsEvent`·`AnalyticsPort` 타입은 있으나
> BE 턴 경로(오케스트레이터·내부 API)에 **이벤트 발행 싱크가 아직 없다.** 배선은 별도 작업
> (권장: LLM prose §8~11과 함께 — 그때 퍼널·전환 신호가 의미를 가짐). 의도된 보류.

> **기반 문서 (공유).** FE↔BE가 같은 이벤트명을 쓰도록 하는 **분석 이벤트 계약**(R28).
> 타입은 `docs/data-model.md`(`AnalyticsEvent`·`AnalyticsPort`), 파이프라인은
> `docs/architecture.md` §11, 시나리오는 `specs/mvp-concierge/scenarios/`.
> 이벤트명/스키마가 바뀌면 **이 문서를 갱신**한다(FE/BE 동시 영향).
> 주요 결정의 후보안·근거는 `docs/adr/`(ADR-0037~0039)에 기록.

## 1. 목표 ↔ 데이터

| 알고 싶은 것 | 기법 | 소스 이벤트 |
|--------------|------|-------------|
| **어디서 이탈?** | 퍼널 | `flow_started/advanced/completed/abandoned` (FlowState 전이) |
| **어떻게 구매?** | 전환 기여 | `message_sent`/`cta_clicked` → `order_confirmed` (`correlation_id`, §5) |
| **어디서 머무름?** | 체류·인게이지먼트 | `screen_viewed`/`screen_exited`(dwell), `template_shown` |

## 2. 공통 스키마 (`AnalyticsEvent`)

```python
{ "event_id": Id,              # 클라이언트/서버 생성 UUID — 멱등 dedup(배치 재시도 중복 제거)
  "schema_version": int,       # 이벤트 스키마 버전 — props 진화 추적
  "sample_rate": float,        # 이 이벤트가 통과한 샘플 비율 — 분석 시 1/rate 재가중(§8)
  "name": str,                 # 택소노미 이벤트명 (§4)
  "ts": datetime,              # UTC
  "session_id": Id,
  "user_ref": str | None,      # 가명화 식별자 (원본 아님, R19)
  "props": dict,               # 이벤트별 속성
  "context": {                 # 공통 맥락
    "screen": str,             # 발생 화면 (S1/S2/S3 …)
    "flow": str | None,        # 진행 흐름 (troubleshoot/order …)
    "flow_step": str | None,
    "correlation_id": Id | None # 기여 추적(대화·CTA→주문 연결, §5)
  } }
```

규칙:
- **동의** — 모든 이벤트는 `Consent.scopes`에 `analytics`가 있을 때만 전송(§6). 식별자는 가명화. 비차단.
- **멱등** — `event_id`로 중복 수집(배치 재전송)을 ingestion에서 제거.
- **버전** — props 변경은 `schema_version`을 올린다(additive-only 원칙(§4)과 병행).

### 네이밍 규칙 (확정)
- **`object_action`(과거형 동사)** 으로 통일한다. 예: `cart_item_added`·`cta_clicked`·`screen_viewed`·`flow_completed`.
- 단일 소유자(§4 owner)만 해당 이벤트를 emit한다(이중 카운트 방지).
- 이벤트는 **추가만**(제거/의미 변경 금지). 이미 라이브면 rename 대신 신규 추가 + 구버전 deprecate.

## 3. 퍼널 정의 (메인 저니)

이탈 측정용 표준 퍼널. 각 단계는 `flow_step`으로 매핑된다.

```
선제 알림 노출 → 채팅 진입 → 진단 → 해결 가이드 → 부품 제시
  → [장바구니] → 결제 확인(R17) → 주문 완료 → (사후 확인 R25)
```
- 각 단계 전이에 `flow_advanced`(props.step) → 단계별 진입/완료율·**drop-off** 산출.
- `flow_abandoned`: 흐름 미완료 종료(이탈 지점 = props.`last_step`).

**브릿지 퍼널** — `card_tapped → bridge_viewed → (bridge_cta_clicked | bridge_escalated | bridge_dismissed)`.
`bridge_dismissed`는 **간단 정보로 충분**(긍정 신호), `bridge_escalated`는 대화가 필요했던 비율 → 브릿지/패널 분기 기준 튜닝에 사용.
`card_type` 값은 `response-templates.md` §9 카드 타입과 동일: `device_status`·`anomaly`·`recommendation`·`order`·`booking`·`warranty`·`notice`·`shortcut`.

## 4. 이벤트 카탈로그

`owner` = **단일 소유자**(그 이벤트를 emit하는 쪽). 이중 카운트 방지를 위해 한 이벤트는 한 쪽만 emit한다.

| 이벤트 | owner | 주요 props | 용도 |
|--------|-------|-----------|------|
| `screen_viewed` | FE | `screen` | 체류·진입 |
| `screen_exited` | FE | `screen`, `dwell_ms` | **체류 시간** |
| `chat_opened` | FE | `entry`(home/cs/fab) | 진입 분석 |
| `card_tapped` | FE | `card_type` | 브릿지 퍼널 진입(R9) |
| `bridge_viewed` | FE | `card_type`, `dwell_ms` | 브릿지 노출·체류 |
| `bridge_cta_clicked` | FE | `cta`, `correlation_id` | 브릿지에서 즉시 행동 |
| `bridge_escalated` | FE | `correlation_id` | 브릿지→AI 패널 전환(P→R) |
| `bridge_dismissed` | FE | `card_type` | 브릿지로 충분(이탈 아님) |
| `message_sent` | FE | `modality`(text/image), `correlation_id` | 인게이지먼트(대화 기여 시작, §5) |
| `template_shown` | FE | `kind` | 어떤 템플릿이 노출 |
| `cta_shown` | FE | `cta`, `template` | CTA 노출(기여 분모) |
| `cta_clicked` | FE | `cta`, `template`, `correlation_id` | **CTA 기여 시작** |
| `flow_started` | BE | `flow` | 퍼널 진입 |
| `flow_advanced` | BE | `flow`, `step` | 퍼널 단계 |
| `flow_completed` | BE | `flow` | 퍼널 완료 |
| `flow_abandoned` | BE | `flow`, `last_step` | **이탈 지점** |
| `cart_item_added` | BE | `part_id` | 주문 퍼널(분석 이벤트 — CTA 액션 `add_to_cart`와 구분) |
| `checkout_shown` | FE | `correlation_id` | 결제 확인 노출(R17) |
| `order_confirmed` | BE | `order_id`, `correlation_id` | **전환(구매)** |
| `order_cancelled` | BE | `order_id` | 취소율(R21) |
| `notification_delivered` | BE | `type`, `priority` | 선제 도달(R20·R26) |
| `notification_opened` | FE | `type` | **선제 효과** |
| `notification_dismissed` | FE | `type` | 알림 피로 신호 |
| `handoff_started` | BE | `type`(agent/visit) | 핸드오프율(R18) |
| `resolution_confirmed` | FE | `resolved`(bool) | 해결률(R25) |
| `fallback_shown` | FE | `reason`(out_of_stock 등), `template` | **R13 폴백률**(UX 건강) |
| `error_shown` | FE | `code`(stream_interrupted·orchestrator_error 등) | **에러 노출률**(스트림 인터럽트 등) |

> `flow_*` owner는 **BE**(FlowState 진실의 출처 = 오케스트레이터). FE도 흐름을 추적하지만 분석 emit은 안 한다(이중 카운트 방지).
> `error_shown`/`fallback_shown`은 **사용자에게 노출된 순간** FE가 emit. **지연(TTFB·완료시간)은 분석이 아니라 운영 메트릭**(operations §5)으로 분리.
> 이벤트는 **추가만**(제거/의미 변경 금지) — 라이브 후 rename 금지(§2 네이밍 규칙은 런칭 전 확정분).

## 5. 전환 기여 (Attribution)

**`correlation_id`는 turn/flow 시작 시 발급**(대화 자체를 1급 기여 채널로). 이후 `cta_clicked`·`checkout_shown`·`order_confirmed`까지 **동일 ID 전파**.

- **대화 기반 전환(핵심)** — 버튼 없이 대화로 주문(자유 텍스트 "주문해줘")해도 `message_sent`→`order_confirmed`가 같은 `correlation_id`로 이어져 기여가 잡힌다. (현행 cta_click-only는 이 경로가 0으로 샜다.)
- **last-touch** — `order_confirmed`를 유발한 경로에 CTA가 있으면 **마지막 `cta_clicked`의 `cta`/`template`** 으로, CTA가 없으면 **대화(organic chat)** 채널로 기여.
- **분모** — `cta_shown`(노출) → CTA별 클릭률·전환율. 대화 채널 분모는 `chat_opened`/`message_sent`.

## 6. 프라이버시 / 동의 (R19)

- **동의 취득 시점** — `analytics` scope 동의는 **회원가입 시 취득**(로그인 사용자는 동의 전제). 따라서 별도 "동의 전 익명 집계"는 두지 않는다(가입 전/비로그인은 분석 비범위).
- `Consent.scopes`에 **`analytics` 미포함(또는 opt-out)이면 수집 안 함**. opt-out 시 즉시 중단(`useAnalytics` no-op).
- `user_ref`는 **가명화**(원본 식별자·연락처·결제정보 금지). `props`에 민감정보 금지.
- 삭제 요청 시 분석 데이터도 cascade 대상(R19, `ConsentPort.delete_data`).

## 7. 수집 / 전송

- **FE** — 화면·CTA·dwell 이벤트를 모아 **배치 전송**(`AnalyticsPort.track_batch`). 네트워크 실패는 무시/재시도(비차단).
- **BE** — 서버 확정 이벤트(`order_confirmed`·`notification_*`)는 직접 emit.
- **MVP** — `MockAnalyticsPort`(로컬 로그). **실** — 분석 플랫폼/웨어하우스(`architecture.md` §11).

## 8. 샘플링 (세션 일관, 적용)

고빈도 저단가 이벤트(`screen_viewed`·`template_shown`·`cta_shown`·dwell)의 볼륨·비용을 제어한다.

- **세션 일관 샘플링(핵심)** — `hash(session_id) < sample_rate`로 **세션 단위**로 수집 여부 결정. 수집 대상 세션은 **모든 이벤트를 다** 보낸다 → **퍼널 무결성 보존**.
  - (이벤트별 랜덤 샘플링은 `cta_clicked`는 남고 `order_confirmed`는 버려질 수 있어 퍼널이 깨짐 → **금지**.)
- **중요 이벤트 100%(allowlist)** — 샘플링과 무관하게 항상 전송: `order_confirmed`·`order_cancelled`·`error_shown`·`fallback_shown`·`flow_abandoned`·`handoff_started`·`resolution_confirmed`.
- **드롭보다 클라 집계** — dwell heartbeat는 **합산 1개**, impression은 **배치 카운트**(정보 손실 없이 볼륨↓).
- **재가중** — 이벤트에 `sample_rate` 기록 → 분석 시 1/rate scale-up(모수 보정).
- **기본값** — `sample_rate`는 환경값(MVP 기본 **1.0=전수**), 고빈도 비용 문제 시 하향. (메커니즘은 적용된 상태.)

> 근거·대안: ADR-0041.

## 9. 비범위 (후속)

- 실시간 대시보드·세션 리플레이·히트맵, A/B 테스트 프레임워크.
- 서버 웨어하우스 스키마·ETL은 실 연동 시 확정.

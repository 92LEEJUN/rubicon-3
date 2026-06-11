# 응답 템플릿 규칙 (Response Templates)

> **기반 문서 (공유).** FE↔BE가 공유하는 **응답 표현 계약**을 정의한다.
> 요구사항 R10(멀티모달)·R11(템플릿·CTA)을 충족한다. 데이터 타입은 `docs/data-model.md`,
> 전체 아키텍처는 `docs/architecture.md` 를 본다. 템플릿 종류·스키마·선택 규칙이 바뀌면
> 스펙 design이 아니라 **이 문서를 갱신**한다.

## 1. 개요 / 원칙

- 응답은 평문이 아니라 **구조화된 `Template` 모델**로 전달하고, **렌더링은 FE가** 담당한다(UI 디커플링).
- 한 응답(`Message`)은 `template` 하나 + `ctas[]` + (선택)`media[]` 로 구성된다.
- LLM 서비스는 답변을 **kind + data** 로 구조화하고, 오케스트레이터가 CTA·미디어를 채운다.
- **확장은 추가만.** FE가 모르는 `kind`/스키마는 거부하지 않고 **`text` 로 폴백**한다.

## 2. 템플릿 카탈로그

| kind | 용도 | 기본 CTA | 요구사항 |
|------|------|----------|----------|
| `text` | 일반 답변, 폴백 | – | R1 |
| `guide_steps` | 단계별 해결 가이드 | (필요 시) `add_to_cart` | R3·R10 |
| `product_card` | 제품/부품 단건 | `add_to_cart`·`reorder` | R4·R8 |
| `product_comparison` | 다건 비교 표 | `add_to_cart`(행별) | R8 |
| `device_status` | 기기 상태·이상 요약 | `reorder`·가이드 연결 | R2·R5 |
| `order_summary` | 장바구니/주문 요약 | `checkout`(확인) | R4·R17 |
| `handoff_card` | 상담원/방문 안내 | `connect_agent`·`request_visit` | R18 |
| `recommendation_list` | 개인화 추천 목록 | `add_to_cart`(항목별) | R8 |
| `choices` | 후보/옵션 중 선택 (명확화) | 선택 시 payload 회신 | R4·R6·R7 |
| `confirmation` | 되돌릴 수 없는 행동 확인 | 확정/취소 | R17 |
| `booking` | 방문 날짜·시간 슬롯 선택 | `request_visit`(슬롯 확정) | R18 |
| `status_tracker` | 주문·방문 진행 상태/이력 | (상세 보기) | R12 |
| `home_summary` | 홈 진입 종합 요약·선제안 | 항목별 CTA | R9·R5 |

> **출력 vs 인터랙션** — 위 카탈로그는 출력형(읽기)과 **인터랙션형**(`choices`·`confirmation`·`booking`,
> 사용자 입력을 회신받음)을 함께 포함한다. 인터랙션 회신 처리는 §8 을 본다.
> 새 kind 추가 시: **이 문서 + `Template.kind`(data-model) + FE 렌더러**를 함께 갱신한다.

## 3. 템플릿별 data 스키마 (의사 타입)

```python
# guide_steps
{ "title": str, "steps": [ { "order": int, "instruction": str, "media": [Media] } ],
  "required_parts": [PartRef] }              # 부품 필요 시 product_card/CTA로 연결

# product_card
{ "product": { "id": Id, "name": str, "model": str, "price": int,
               "image": Media | None, "in_stock": bool } }

# product_comparison
{ "columns": [str],                          # 비교 항목(가격·스펙 등)
  "rows": [ { "product": ProductRef, "values": { col: str } } ] }

# device_status
{ "device": { "id": Id, "name": str, "status": str },
  "anomalies": [ { "type": str, "severity": "info|warning|critical", "detail": str } ],
  "consumables": [ { "name": str, "life_remaining": float } ] }

# order_summary
{ "items": [ { "part": PartRef, "qty": int, "price": int } ],
  "total": int, "requires_confirmation": bool }   # R17

# handoff_card
{ "reason": str, "options": ["agent" | "visit"], "context_ref": Id }

# recommendation_list
{ "items": [ { "product": ProductRef, "reason": str } ] }   # reason = 개인화 근거(R8)

# choices  — 옵션 중 택1/택N. 선택 결과는 후속 요청으로 회신(§8)
{ "prompt": str,
  "options": [ { "id": str, "label": str, "detail": str | None, "ref": Id | None } ],
  "multi": bool }                            # 다중 선택 허용 여부

# confirmation  — 되돌릴 수 없는 행동 확인 (R17). ActionGate 와 연동
{ "action": str,                             # 예: "checkout"
  "summary": str,                            # 무엇을 확정하는지
  "payload": dict,                           # 실행에 필요한 식별자
  "confirm_label": str, "cancel_label": str }

# booking  — 방문 예약 슬롯 (R18)
{ "service_type": "visit",
  "slots": [ { "id": str, "start": datetime, "end": datetime, "available": bool } ],
  "context_ref": Id }

# status_tracker  — 진행 상태/이력 (R12)
{ "subject": "order" | "service", "ref_id": Id,
  "state": str,                              # 예: confirmed | in_progress | done
  "steps": [ { "label": str, "done": bool, "at": datetime | None } ] }

# home_summary  — 홈 진입 종합 (R9·R5)
{ "alerts": [DeviceStatusRef],               # 이상/소모품 선제 알림
  "recommendations": [ProductRef],
  "shortcuts": [ { "label": str, "intent": str } ] }
```

> `ProductRef`/`PartRef` 는 식별자 + 표시용 최소 필드. 상세 타입은 `docs/data-model.md`.

## 4. CTA 매핑 규칙 (R11·R17)

| 템플릿 | 허용 CTA |
|--------|----------|
| `product_card` / `recommendation_list` | `add_to_cart`, `reorder` |
| `product_comparison` | `add_to_cart`(행별) |
| `order_summary` | `checkout` |
| `device_status` | `reorder`, (가이드 연결) |
| `handoff_card` | `connect_agent`, `request_visit` |
| `choices` | 옵션 선택(=payload 회신) |
| `confirmation` | 확정/취소 — `ActionGatePort` 연동(R17) |
| `booking` | `request_visit`(슬롯 확정) |
| `status_tracker` | (상세/이력 보기) |
| `home_summary` | 항목별 CTA(`reorder`·`add_to_cart`·가이드 연결) |

- **되돌릴 수 없는 CTA**(`checkout` 등)는 `confirmation`/`ActionGatePort` 확인을 거친다(R17).
- CTA `payload` 에는 실행에 필요한 식별자만 담는다(예: `{"order_id": ...}`).

## 5. 템플릿 선택 규칙 (의도 → 템플릿)

| 의도(IntentType) / 상황 | 기본 템플릿 |
|--------------------------|-------------|
| `DEVICE_STATUS` | `device_status` |
| `TROUBLESHOOT` | `guide_steps` (부품 필요 시 `product_card` 연결) |
| `ORDER` | `product_card` → `order_summary` |
| `RECOMMEND` | `recommendation_list` 또는 `product_comparison` |
| `GENERAL` / 분류 실패 | `text` |
| 선제 알림(R5) | `device_status` + `reorder` CTA |
| 홈 첫 진입(R9-2) | `home_summary` |
| 후보 모호(R4-3)·의도 불명확(R7)·흐름 전환 확인(R6.5) | `choices` |
| 되돌릴 수 없는 행동 직전(R17) | `confirmation` |
| 방문 요청 확정 단계(R18) | `booking` |
| 주문/서비스 진행·이력 조회(R12) | `status_tracker` |

- **복합 질문(R7)** — 의도별 템플릿을 **섹션으로 묶어** 반환하고, `unhandled` 의도는 `text` 로 안내.
- 동일 답변에 텍스트 설명 + 템플릿을 함께 줄 수 있다(텍스트는 `Message.text`, 구조는 `template`).

## 6. 멀티모달 포함 규칙 (R10)

- 시각 자료가 도움이 되면 해당 필드에 `Media`(이미지/영상)를 포함한다.
  - `guide_steps.steps[].media`, `product_card.product.image` 등.
- `Media` 는 형식·크기 제한을 따른다(`docs/data-model.md` §0·`Media`).

## 7. 폴백 · 검증 규칙

- FE가 **모르는 `kind`** → `text` 로 렌더(`data.text` 또는 평문).
- `data` 가 kind **스키마와 불일치** → `text` 폴백 + 로깅(관측성).
- 템플릿 생성 실패/부분 → 최소한 `text` 응답은 보장(전체 대화 중단 금지, R13).

## 8. 인터랙션 응답 (입력 회신)

`choices`·`confirmation`·`booking` 등 **인터랙션형 템플릿**은 사용자의 선택을 **후속 요청으로 회신**받는다.

- 회신은 기존 대화 경로(`ChatRequest`)로 보내며, 무엇을 선택했는지 식별 정보를 담는다.
  - `choices` → 선택한 `option.id`(다중이면 목록)
  - `confirmation` → 확정/취소 + 원본 `payload`
  - `booking` → 선택한 `slot.id` + `context_ref`
- 오케스트레이터는 회신을 **진행 중 흐름(`FlowState`)에 반영**해 다음 단계로 잇는다(R6·R7).
- 확정형 회신(`confirmation`/`booking` 확정)은 **되돌릴 수 없는 행동**일 수 있으므로
  `ActionGatePort` 규칙을 따른다(R17).
- 사용자가 응답하지 않거나 다른 주제로 전환하면, 인터랙션은 **흐름 보류(suspended_flow)** 로 두고
  자유 대화로 진행할 수 있다(R6).

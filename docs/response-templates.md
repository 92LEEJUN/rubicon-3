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
| `bridge` | 카드 탭 시 경량 설명 모달(컨테이너) | 즉시 CTA + AI 에스컬레이션 | R9 |

> **출력 vs 인터랙션 vs 브릿지** — 출력형(읽기), **인터랙션형**(`choices`·`confirmation`·`booking`,
> 입력 회신, §8), **브릿지형**(`bridge`, 카드 탭 단발 모달 — §9)을 포함한다.
> 새 kind 추가 시: **이 문서 + `Template.kind`(data-model) + FE 렌더러**를 함께 갱신한다.

> **종합 내러티브(compose, ADR-0053).** 슈퍼바이저가 복합 턴의 섹션들을 자연어로 정리한 **선두 내러티브**는
> **신규 kind 없이 `text`를 재사용**한다(`intent="narration"`, `data.composed=true`·`data.prose=true`).
> FE는 기존 text 렌더러로 그대로 표시 → **계약 추가 없음**. 내러티브는 뒤따르는 구조화 카드/CTA를
> "참조"만 하고 데이터를 재기술하지 않는다(카드는 자기 섹션이 권위 있는 출처).

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

# order_summary  (금액 분해 — C)
{ "items": [ { "part": PartRef, "qty": int, "price": int } ],
  "subtotal": int, "shipping_fee": int, "tax": int, "discount": int,
  "total": int,                                # = subtotal + shipping_fee + tax - discount
  "requires_confirmation": bool }              # R17. 각 금액 ≥ 0 (data-model §0)

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

# bridge  — 카드 탭 경량 설명 모달 (컨테이너, §9)
# 구성: 테두리(chrome) + 본문(detail 재사용) + 액션. detail에 있는 내용은 bridge 레벨에서 중복 금지.
{ "title": str,
  "subtitle": str | None,                    # 부제(기기·카테고리·모델 등)
  "badge": { "label": str, "level": str } | None,  # 상태/심각도: 정상|경고|위험 · 진행중|완료 · 유상|무상(R22)
  "summary": str,                            # 간단 설명 (LLM 생성 가능)
  "highlights": [ { "label": str, "value": str } ] | None,  # 핵심 지표(수명·가격·만료일 등)
  "media": Media | None,                     # 대표 이미지 (detail에 없을 때만)
  "detail": Template | None,                 # 본문 재사용(device_status·product_card·status_tracker 등)
  "meta": { "source": str | None, "at": datetime | None } | None,  # 근거(R16)·시점
  "ctas": [Cta],                             # 주력 행동(주문·예약·재주문 등)
  "secondary": [Cta] | None,                 # 보조(나중에·"이 알림 끄기" R20)
  "escalate": { "label": str, "intent": str } | None }  # "AI에게 물어보기" → /chat(맥락 주입)
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

- **CTA는 두 종류다** (라우팅은 `architecture.md` §8):
  - **대화형 CTA** — 제안 칩, `choices`/`confirmation`/`booking` 회신, 설명 요청. `/chat`으로
    재진입해 흐름(FlowState)을 잇고 **LLM을 탈 수 있다**(§8 인터랙션 응답).
  - **결정적 커밋** — 결제·주문·예약 확정(`checkout` 등). 결정적 엔드포인트로 직행, **LLM 미경유** +
    `confirmation`/`ActionGatePort` 확인(R17).
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
| 홈 카드 탭 — 간단 정보(§9) | `bridge` (모달) |

- **복합 질문(R7)** — 한 어시스턴트 응답을 **의도별 `MessageSection`**(`label·intent·template·ctas·handled`,
  `data-model.md`)으로 묶는다. 단발 응답=섹션 1개, 복합=N개(우선순위 순서). 미처리 의도는 `handled:false`
  섹션(폴백 `text`)으로 구분(R7-3). 스트리밍은 `section` 청크로 순서대로 전달(`api-contract.md` §2.1).
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

## 9. 브릿지 (Bridge) — 카드 탭 경량 모달

홈 카드(또는 알림)를 누를 때, **간단한 정보면 풀 대화(AI 패널) 대신 경량 모달**로 설명한다(R9).
이 모달의 응답이 `bridge` 템플릿이다.

- **컨테이너 = 테두리(chrome) + 본문(detail) + 액션** — bridge 레벨은 `title`·`subtitle`·`badge`·`summary`·
  `highlights`·`meta`(프레이밍)와 `ctas`·`secondary`·`escalate`(액션)를 갖고, **본문은 다른 템플릿을 `detail`로
  끼워** 재사용한다(예: 기기 카드 → `device_status`). **`detail`에 이미 있는 내용은 bridge 레벨에서 중복 금지**
  (예: 이미지가 `product_card`에 있으면 `media` 생략).
- **단발성(single-shot)** — 대화 세션을 열지 않는다. 모달 안에서 끝나거나, 두 갈래 출구로 나간다:
  - **즉시 행동** — `ctas`(주문·예약·재주문 등). 되돌릴 수 없는 커밋은 `confirmation`/ActionGate(R17).
  - **에스컬레이션** — `escalate` → `/chat` 진입(화면 맥락 주입 R9-4). *알림 탭→대화(P→R 전이)와 같은 패턴.*
- **bridge vs AI 패널은 BE가 동적 판단** — 카드 탭은 요청을 보내고, 오케스트레이터가
  **간단(→`bridge` 모달) / 복잡(→대화 패널)** 을 런타임에 결정한다(`architecture.md` §8, FE는 surface만 받아 렌더).
- **콘텐츠 소스** — 결정적 조회(기기·주문 상태 등) + 필요 시 LLM 요약. 무거운 추론은 에스컬레이션으로 넘긴다.
- 퍼널 측정(카드 탭→bridge→에스컬레이션/행동/이탈)은 `docs/analytics.md`.

### 브릿지 콘텐츠 종류 (카드 타입별)

`card_type`(analytics 이벤트 키와 동일)별 `bridge` 구성. `detail`은 기존 템플릿 재사용.

| `card_type` | `summary` (LLM 가능) | `detail` (재사용) | 기본 CTA | `escalate` 의도 | 소스 | 패널 직행 조건 |
|-------------|----------------------|--------------------|----------|------------------|------|----------------|
| `device_status` 기기 상태(정상) | 상태 한 줄 | `device_status` | – | "점검 물어보기" | 결정적 | – |
| `anomaly` 이상/소모품 알림 | 무엇·왜·심각도 | `device_status` | `reorder`(소모품) / 가이드 보기 | "해결 방법" | 결정적+LLM | **위험(R23)·복합 이상 → 패널** |
| `recommendation` 추천 제품 | 추천 이유(R8 근거) | `product_card` | `add_to_cart` | "비교/대안" | 결정적+LLM | 비교·상담 필요 → 패널 |
| `order` 주문/배송 상태 | 진행 한 줄 | `status_tracker` | `cancel_order`(가능 시 R21) | "주문 문의" | 결정적 | 환불·예외 → 패널 |
| `booking` 방문 예약 | 일정·상태 | `status_tracker` | 변경/취소 | "예약 문의" | 결정적 | 일정 협의 → 패널 |
| `warranty` 보증 상태(R22) | 유·무상 요약 | (보증 표현) | 수리/방문 신청 | "보증 문의" | 결정적 | **불확실 → CS/패널** |
| `notice` 공지/FAQ | 안내 요약 | `text` | – | (필요 시) | 정적/결정적 | 추가 질문 → 패널 |
| `shortcut` 바로가기 칩 | — | — | — | — | — | **항상 화면/패널 이동**(bridge 아님) |

- **공통 출구** — 모든 bridge는 `escalate`(→`/chat`, 맥락 주입)를 기본 제공. `card_type`은 분석(`card_tap.card_type`)과 동일 키.
- **패널 직행** — "패널 직행 조건"에 해당하면 카드 탭이 bridge가 아니라 바로 S3로 간다(BE 동적 판단).

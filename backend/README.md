# MVP 컨시어지 — 동작 프로토타입 (OpenAI 소형 모델)

`specs/mvp-concierge/`의 흐름을 **소형 LLM + Mock 어댑터(fixtures)** 로 실제 동작시키는 최소 프로토타입.

## 모델
- 기본 **`gpt-4o-mini`** — 소형·저비용, **function calling + 구조화 출력** 지원(이 기능에 충분).
- 교체: `export LLM_MODEL=gpt-4.1-mini` 등.

## 구조 (architecture.md §4·§9 / orchestration.md 대응)
```
app/
├─ domain/           # 타입 있는 도메인 모델(Pydantic) — 공유 계약(data-model.md)
├─ ports/            # Port Protocol(Device·CSKnowledge·Catalog·Order·Handoff·Warranty)
├─ adapters/mock.py  # Port의 Mock 구현(fixtures→도메인 타입 변환=ACL)
├─ repositories/     # 내부 저장소(EngagementRepository, R29) — 인메모리
├─ services/         # 도메인 서비스(Device·Knowledge·Catalog·Order·Handoff·Notification)
├─ container.py      # Mock 어댑터로 서비스 조립(실 전환=어댑터만 교체)
├─ errors.py         # 도메인 예외(ConfirmationRequired = R17 게이트)
├─ fixtures.py       # 더미데이터 로더 (specs/mvp-concierge/fixtures)
├─ tools.py          # LLM tool 정의 + 디스패치(→ adapters.mock)
├─ orchestrator.py   # ① 의도분류(구조화) → ② tool 호출 루프 → ③ 근거 기반 응답
├─ llm.py            # OpenAI 클라이언트(키=환경변수)
└─ cli.py            # 풀 저니 실행
tests/               # pytest — 도메인 모델·Mock 어댑터·서비스(31 케이스)
```

## 테스트 (TDD)
```bash
pip install -r requirements-dev.txt
python -m pytest          # 모델·Port·서비스·오케스트레이터·내부 API (네트워크 불필요)
```

## 내부 API 서버 (BFF용, api-contract §2.4)
```bash
pip install -r requirements.txt
uvicorn app.api.internal:app --reload --port 8001
```
- WS `/internal/turn` — 자연어 → 오케스트레이터 섹션 스트림(§2.1 봉투)
- `GET /internal/devices`·`/internal/home`·`/internal/catalog/recommend` — 결정적 조회
- `POST /internal/orders` — 커밋 게이트(R17): 미확인 시 **409** + `confirmation` 템플릿
- `GET/POST /internal/bookings` — 방문 슬롯·예약(R18) / `POST /internal/surface` — bridge·panel(§2.3)

> 오케스트레이터 분류기는 기본 **규칙기반(네트워크 불필요)**. LLM 분류는 `OpenAIClassifier`로 교체.

## 실행
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY=sk-...        # 키는 환경변수로만 (저장소에 넣지 않음)
python -m app.cli "세탁기에서 물이 안 빠져요. 해결법과 부품 주문 도와줘"
```

키를 매번 export하기 번거로우면 `backend/.env`(gitignore됨)에 둘 수 있다 — 실행 시 자동 로드된다.
```
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

## 동작 (J1 데모)
의도 분류 → `get_device_status`(세탁기 5C) → `search_solutions`(배수 가이드) →
`match_parts`(배수 필터) → 단계 가이드 + 부품(12,000원) 주문 제안.

> 실 전환: `adapters/mock`을 SmartThings/CS/제품 Real 어댑터로 교체(Port 인터페이스 불변).
> 네트워크: `api.openai.com` 아웃바운드 접근 필요(CLI 데모 한정 — 도메인 테스트는 불필요).

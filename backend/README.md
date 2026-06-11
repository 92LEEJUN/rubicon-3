# MVP 컨시어지 — 동작 프로토타입 (OpenAI 소형 모델)

`specs/mvp-concierge/`의 흐름을 **소형 LLM + Mock 어댑터(fixtures)** 로 실제 동작시키는 최소 프로토타입.

## 모델
- 기본 **`gpt-4o-mini`** — 소형·저비용, **function calling + 구조화 출력** 지원(이 기능에 충분).
- 교체: `export LLM_MODEL=gpt-4.1-mini` 등.

## 구조 (orchestration.md 대응)
```
app/
├─ fixtures.py       # 더미데이터 로더 (specs/mvp-concierge/fixtures)
├─ adapters_mock.py  # Mock Port: get_device_status·search_solutions·match_parts
├─ tools.py          # LLM tool 정의 + 디스패치
├─ orchestrator.py   # ① 의도분류(구조화) → ② tool 호출 루프 → ③ 근거 기반 응답
├─ llm.py            # OpenAI 클라이언트(키=환경변수)
└─ cli.py            # 풀 저니 실행
```

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

> 실 전환: `adapters_mock`을 SmartThings/CS/제품 Real 어댑터로 교체(인터페이스 불변).
> 네트워크: `api.openai.com` 아웃바운드 접근 필요.

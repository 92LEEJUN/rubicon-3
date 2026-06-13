# BFF — 클라이언트 표면 (Backend-for-Frontend)

FE↔BFF↔BE 3계층(`docs/architecture.md` §9)의 **클라이언트 표면** 서비스. FE는 이 서비스만 본다.
클라이언트 계약(`docs/api-contract.md` §2)을 소유하고, **BE 도메인 내부 API**(§2.4)를 중계·정형화한다.

> 비즈니스 로직은 **없다** — aggregation · Template 변환 · 인증 게이트 · 스트리밍 중계 · 폴백 정규화만.

## 구조
```
gateway/
├─ main.py            # FastAPI 앱 — 클라이언트 표면(WS /chat·HTTP), create_app(backend) 팩토리
├─ backend_client.py  # BE 내부 API 클라이언트(httpx.AsyncClient, ASGITransport 주입 가능)
├─ auth.py            # 인증/세션 게이트(Mock 토큰 → 사용자 컨텍스트, §3)
├─ transform.py       # 폴백 정규화(R13)·인터랙션 회신→텍스트
└─ config.py          # BE_BASE_URL 등
tests/                # 엔드포인트·WS·계약(FE↔BFF↔BE 인프로세스)·신원/게스트·폴백 (45 케이스)
```

## 클라이언트 표면 (api-contract §2)
| 엔드포인트 | 설명 |
|------------|------|
| WS `/chat` | 자연어/인터랙션 회신 → BE 섹션 스트림 중계(§2.1) |
| `GET /devices`·`/devices/{id}`·`/home`·`/catalog/recommend` | 결정적 조회(§2.2) |
| `POST /orders` | 커밋 게이트(R17) — 미확인 시 **409** + `confirmation` 그대로 중계 |
| `GET/POST /bookings` | 방문 슬롯·예약(R18) |
| `POST /surface` | 카드 탭 → bridge/panel(§2.3) |

- 모든 HTTP는 **인증 게이트**(Authorization 헤더, Mock) — 없으면 401.
- 업스트림(BE) 장애는 **폴백 응답**(`{code, message, fallback}`)으로 정규화(R13).

## 실행
```bash
pip install -r requirements.txt
# BE 도메인(별도 서비스) 주소
export BE_BASE_URL=http://localhost:8001
uvicorn gateway.main:app --reload --port 8000
```

## 테스트 (TDD · 계약)
```bash
pip install -r requirements-dev.txt
pip install -r ../backend/requirements.txt    # 계약 테스트가 BE를 인프로세스 import
python -m pytest
```
- **계약 테스트** — `BackendClient`를 httpx ASGITransport로 BE 앱에 인프로세스 연결해
  FE↔BFF↔BE를 **실제 HTTP 계약**으로 검증(별도 서버 불필요, api-contract §5).

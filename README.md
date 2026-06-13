# 삼성 AI 컨시어지 — MVP

가전 **이상 감지 → 해결 가이드 → 부품 주문**을 잇는 AI 컨시어지. **FE / BFF / BE 3계층**(모두
이 저장소) 모노레포이며, spec-driven 워크플로우로 문서를 먼저 잡고 TDD로 구현했다.

- **라이브 데모(설치 불필요)**: https://92leejun.github.io/rubicon-3/ — 홈·채팅·갤러리·아키텍처 문서 탭이 **BE 없이 mock 모드**로 동작.
- 상세 설계는 [`docs/`](./docs) · 작업 규칙은 [`CLAUDE.md`](./CLAUDE.md).

## 구조
```
FE (frontend/)  →  BFF (bff/)  →  BE (backend/)
react-native-web   FastAPI         FastAPI
:5173 (vite)       :8000           :8001
렌더러·트랜스포트   중계·인증·신원   오케스트레이터·도메인·Port(Mock)
```
| 모듈 | 내용 | 테스트 | 상세 |
|---|---|---|---|
| `backend/` | 도메인·오케스트레이터(capability·LLM 플래너)·멀티테넌트·내부 API | `pytest` 233 | [README](./backend/README.md) |
| `bff/` | 클라이언트 표면(WS `/chat`·HTTP)·인증·신원 중계 | `pytest` 45 | [README](./bff/README.md) |
| `frontend/` | RN(Web) 앱·템플릿 렌더러·mock 모드 | `jest` 84 | [README](./frontend/README.md) |
| `e2e/` | FE↔BFF↔BE 풀스택 시나리오(Playwright) | — | [README](./e2e/README.md) |

## 빠른 시작

### A. 정적 데모만 (설치 0)
위 라이브 데모 URL 접속. 또는 `cd frontend && npm install && npm run dev` 후 http://localhost:5173 — **BE 없이 mock 모드**로 전부 동작(채팅·주문·예약은 localStorage). `?mock=1` 강제, `?reset=1` 초기화.

### B. 로컬 풀스택 (BE+BFF+FE)
터미널 3개:
```bash
# 1) BE  (:8001)
cd backend && pip install -r requirements.txt && uvicorn app.api.internal:app --reload --port 8001

# 2) BFF (:8000)  — BE를 가리킴
cd bff && pip install -r requirements.txt && BE_BASE_URL=http://localhost:8001 uvicorn gateway.main:app --reload --port 8000

# 3) FE  (:5173)
cd frontend && npm install && npm run dev
```
실 BE 연결 채팅: http://localhost:5173/?screen=live&api=http://localhost:8000&ws=ws://localhost:8000/chat?token=demo

### CLI (BE 단독 데모)
```bash
cd backend && python -m app.cli "세탁기에서 물이 안 빠져요. 해결법과 부품 주문 도와줘"
```

## 테스트
```bash
cd backend  && pip install -r requirements-dev.txt && python -m pytest          # 233
cd bff      && pip install -r requirements-dev.txt -r ../backend/requirements.txt && python -m pytest   # 45 (BE 인프로세스 import)
cd frontend && npx jest                                                          # 84
cd e2e      && npm install && npm --prefix ../frontend install && npm test       # 세 서비스 자동 기동 후 풀스택
```

## 환경 변수 / 토글
`.env`(gitignore)나 셸 env로 주입. **모든 토글 기본 off = 기존 동작 불변**.
| 변수 | 용도 |
|---|---|
| `OPENAI_API_KEY` | 실 LLM(`gpt-4o-mini`). 없으면 규칙 폴백 — `backend/.env` |
| `LLM_BACKED` | LLM 플래너 라우팅 on (off면 규칙 폴백) |
| `CAPABILITY_ORCH` / `MULTIAGENT` | 오케스트레이터 경로 선택 |
| `MULTITENANT` | Principal/게스트 신원 해석 (off면 기본 사용자) |
| `PERSISTENCE=memory\|db` (+`SQLITE_PATH`) | 상태 영속 |
| `BE_BASE_URL` | BFF가 가리킬 BE 주소 |

## 배포
- **GitHub Pages** (FE 정적, mock 모드): `main` 푸시 시 `.github/workflows/deploy-pages.yml`가 `frontend/dist`를 **gh-pages 브랜치로 발행**. 최초 1회 **Settings → Pages → Source = "Deploy from a branch" → `gh-pages` /(root)**. 배포 URL: https://92leejun.github.io/rubicon-3/
- **Vercel**: 저장소 연결 시 `vercel.json`로 `frontend/dist` 빌드.
- **BE/BFF**(실 서비스): 각각 `uvicorn` ASGI 앱(`app.api.internal:app` / `gateway.main:app`)을 컨테이너/호스트에 배포, BFF에 `BE_BASE_URL` 주입.

## 문서
- 기반 문서 [`docs/`](./docs) — architecture·data-model·api-contract·{backend,bff,frontend}-architecture·orchestration·operations·llm-policy 등, 결정 기록 [`docs/adr/`](./docs/adr)(0043~), 확장 로드맵 [`docs/roadmap.md`](./docs/roadmap.md).
- 스펙 [`specs/`](./specs) — mvp-concierge·capability-orchestrator·multi-tenant-state·fe-mock-mode·trust-safety-baseline.

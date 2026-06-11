# 삼성 AI 컨시어지 — MVP

가전 **이상 감지 → 해결 가이드 → 부품 주문**을 잇는 AI 컨시어지 MVP.
스펙 기반(spec-driven) 워크플로우로 문서를 먼저 잡고, **FE / BFF / BE 3계층**을 TDD로 구현했다.

## 라이브 데모
- **GitHub Pages**: `https://92leejun.github.io/rubicon-3/` (정적 데모 — 홈·템플릿 갤러리·Mock 채팅, 백엔드 불필요)
  - 최초 1회: 저장소 **Settings → Pages → Source = "GitHub Actions"** 설정 후 `main` 푸시 시 자동 배포.
  - 라이브 채팅(실 BE 연결)은 `?screen=live&ws=<BFF WebSocket URL>`.
- **Vercel**: 저장소 연결 시 `vercel.json`로 바로 빌드(루트 디렉터리 그대로).

## 구조 (3계층 분리 — `docs/architecture.md` §9)
```
FE (frontend/)  →  BFF (bff/)  →  BE (backend/)
react-native-web    FastAPI         FastAPI
One UI · 템플릿      클라이언트 표면   오케스트레이터·도메인·Port(Mock)
렌더러·트랜스포트    중계·인증·정형화   의도분류·복합분해(R7)·LLM(소형)
```

| 모듈 | 내용 | 테스트 |
|------|------|--------|
| `backend/` | 도메인·Port(Mock)·오케스트레이터·내부 API | pytest **52** |
| `bff/` | 클라이언트 표면(WS `/chat`·HTTP)·인증·폴백 | pytest **16** |
| `frontend/` | RN(Web) 앱·One UI·템플릿 렌더러·WS 트랜스포트 | jest **20** |
| `e2e/` | FE↔BFF↔BE 풀스택 J1~J5(Playwright) | **8** |

> 각 모듈 README에 실행/테스트 방법이 있다. 전체 E2E: `cd e2e && npm test`(세 서비스 자동 기동).

## 문서
- **기반 문서** `docs/` — architecture·data-model·api-contract·response-templates·frontend-architecture·orchestration·analytics·wireframes
- **스펙** `specs/mvp-concierge/` — requirements(R1~R29)·design·journeys(J1~J5)·tasks·fixtures
- **작업 규칙** `CLAUDE.md` / 사람용 `docs/WORKFLOW.md`

## LLM / 보안
- 오케스트레이터 분류기는 기본 **규칙기반(네트워크 불필요)**. LLM 분류·CLI 데모는 OpenAI 소형 모델(`gpt-4o-mini`).
- 키는 **`OPENAI_API_KEY` 환경변수/`.env`(gitignore)만** — 저장소·코드 미포함.

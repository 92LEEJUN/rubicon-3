# FE — React Native (Web) 앱

삼성 AI 컨시어지 앱. **React Native 컴포넌트**(웹 타깃=react-native-web)로 작성해 모바일/웹 공용.
**BFF만 호출**(api-contract §2). Samsung One UI 스타일 디자인 토큰(애셋 도착 시 값만 교체).

## 구조 (frontend-architecture.md §10)
```
src/
├─ design/tokens.ts      # One UI 토큰(색·간격·타이포·radius)
├─ components/           # 프리미티브(Card·Button·Badge…) + 섹션/메시지 렌더
├─ templates/            # kind → 컴포넌트 레지스트리(§4) + text 폴백(§7)
├─ screens/              # S1 Home · S3 ChatPanel
├─ state/                # 채팅 reducer(청크→섹션 누적) + useChat 훅(§11)
├─ transport/            # ChatTransport 추상화 + WebSocket·Mock 구현(§5)
├─ types/contract.ts     # FE↔BFF 계약 타입(api-contract §2)
└─ fixtures/             # 데모/스크린샷/테스트용 섹션(BE 출력과 동형)
```

## 개발/테스트
```bash
npm install
npm test               # Jest + Testing Library(react-native-web) — 렌더러·reducer·화면
npm run dev            # Vite 개발 서버(웹)
```

## 스크린샷 (PR 첨부)
```bash
npm run build
npx playwright install chromium
npm run screenshots    # __screenshots__/home.png · chat-j1.png
```
- `?screen=home|chat` 으로 화면 선택. 헤드리스 크로미움으로 캡처.

## 결정/적응
- **트랜스포트=WebSocket**(→ BFF `/chat`), `ChatTransport` 추상화 뒤(§5). 테스트/오프라인은 `MockTransport`.
- 테스트는 **Testing Library + react-native-web**(웹 DOM 렌더) — 스크린샷/E2E 타깃과 일관(웹 우선).
- 복합 응답(R7)은 `section` 청크를 reducer로 누적해 섹션을 세로 스택, 미처리(`handled:false`) 표시.

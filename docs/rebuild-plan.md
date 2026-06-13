# 재구축 계획 (Rebuild Plan) — bottom-up PR 시퀀스

> 현 시점 산출물을 **바닥부터 다시** 만든다면의 최소 PR 시퀀스와 PR별 요구사항. 이번 세션의
> "되돌린 결정"(에스컬레이션 게이트·core 중복·FE/BFF 드리프트·CI 후행)을 **앞단 설계로 흡수**해
> 재작업을 줄인 순서다. 각 PR은 **독립 green·리뷰·롤백 단위**, 신기능은 **토글 default-off**.

## 순서 원칙
1. **CI·린트·툴링을 PR1에** — 게이트 먼저.
2. **capability 단일 백본을 처음부터** — core 별도 구현→수렴/제거 왕복 제거.
3. **LLM 플래너 단일 라우터를 처음부터** — 에스컬레이션 게이트 도입→폐기 왕복 제거.
4. **계약 변경은 수직 슬라이스(BE+BFF+FE 한 PR)** — 계층 드리프트 방지.
5. **ADR은 결정과 동시에** PR에 동봉.

권장 **11 PR**(아래). 압축 시 최소 **8 PR**(§압축 매핑).

---

## PR1 — 스캐폴딩 + CI + 툴링 + 기반 문서
**목표:** 빈 모노레포에 게이트·문서 골격.
- [ ] `backend/ bff/ frontend/ e2e/` 디렉토리 + 각 README 스텁.
- [ ] 기반 문서 `docs/`(architecture·data-model·api-contract·response-templates·frontend-architecture·orchestration·operations·llm-policy·analytics·wireframes) + `CLAUDE.md`·`docs/WORKFLOW.md`·`docs/adr/README.md`.
- [ ] **CI `.github/workflows/ci.yml`** — be/bff/fe 테스트 + 빌드 + lint(빈 상태라도 통과).
- [ ] 툴링: `pyproject.toml`(ruff)·eslint/prettier·`.editorconfig`·`.pre-commit-config.yaml`·`.env.example`·`Dockerfile`×3·`compose.yml`.
- **게이트:** CI green(테스트 0개라도). **의존:** 없음.

## PR2 — BE 도메인 + Port/Mock 어댑터 + 서비스
**목표:** 결정적 도메인 코어.
- [ ] `data-model.md`의 모델(pydantic)·Repository/Port 인터페이스.
- [ ] Mock 어댑터(device·knowledge·catalog·order·handoff·store·warranty) + 인메모리 리포(**user_id 키잉**).
- [ ] 서비스(device·knowledge·catalog·order(R17 게이트)·handoff·triage·recommendation·companion).
- [ ] `Container`/`build_container()`.
- **게이트:** `cd backend && pytest`(도메인·서비스). **의존:** PR1.

## PR3 — BE 오케스트레이터(결정적) + 내부 API
**목표:** mvp-concierge 핵심 — 자유텍스트 → §2.1 봉투.
- [ ] 규칙 분류기 + **capability 레지스트리(조언형/행동형, 단일 백본)** + handlers.
- [ ] 수리 CTA 게이팅(위험·보증 무상 → 부품 CTA 숨김 + 안내), 복합 fan-out, handled/unhandled.
- [ ] 내부 API(WS/HTTP `/turn` 스트림·`/orders` 커밋 게이트 409·`/bookings`·조회·surface·home).
- [ ] ADR: 조언형/행동형 분리.
- **게이트:** pytest(오케스트레이터·내부 API). **의존:** PR2.

## PR4 — 수직 슬라이스: 응답 계약 + BFF + FE 골격
**목표:** FE↔BFF↔BE 한 번에(계약 동기화).
- [ ] `response-templates.md` + `frontend/src/types/contract.ts`(템플릿·CTA kind·청크·ClientMessage).
- [ ] BFF 게이트웨이: WS `/chat`·HTTP 중계·인증·폴백 정형화.
- [ ] FE: RN-web 앱·디자인 토큰·템플릿 렌더러·트랜스포트(WS+Mock 폴백)·홈/고객지원/채팅 화면·`useChat`.
- **게이트:** be/bff pytest + fe jest + build. **의존:** PR3.

## PR5 — E2E(Playwright) 풀스택
- [ ] `e2e/` — 세 서비스 자동 기동, J1~J5 시나리오(진단→주문·추천·예약·복합).
- **게이트:** `cd e2e && npm test`. **의존:** PR4.

## PR6 — LLM 플래너 단일 라우터 + 목적지 capability
**목표:** LLM 라우팅(게이트 없이 처음부터 단일 라우터).
- [ ] `LLMPlanner`(구조화 출력) — **모든 질의 라우팅**, 규칙은 폴백. `LLM_BACKED` 토글(off=규칙).
- [ ] capability 추가: warranty·booking·explain·clarify(+게이팅), 플래너 결과 캐시.
- [ ] 정본 테스트셋(`test-set.md`) + 실 LLM 수동 하니스(`verify_*`). ADR: 단일 라우터.
- **게이트:** pytest(stub 플래너 결정적) + 회귀(토글 off). **의존:** PR3.

## PR7 — 멀티테넌트 + 신원 계약(3계층)
**목표:** Principal/게스트 격리(BE+BFF+FE 동기화).
- [ ] BE: `Principal(user|guest)`·신원 해석·게스트 커밋 게이트(401). `MULTITENANT` 토글.
- [ ] BFF: 헤더(`X-User-Id`/`X-Guest-Token`)·WS payload 신원 전달·게스트 허용·401/409 중계.
- [ ] FE: 커밋 게이트(409 확인·401 로그인 월)·신원 전달. ADR: 신원·커밋 계약.
- **게이트:** be/bff/fe 테스트(격리·게스트·회귀). **의존:** PR4, PR6.

## PR8 — 영속 + 동시성 + 관측
- [ ] sqlite 어댑터(상태 리포, `PERSISTENCE=memory|db` + `SQLITE_PATH`) — Port 동일·계약 테스트 파라미터화.
- [ ] read-modify-write 동시성(KeyedLock).
- [ ] `/health`·`/metrics`(Prometheus, stdlib) + 구조화 로깅.
- **게이트:** be/bff pytest(+영속 복원·동시성). **의존:** PR7.

## PR9 — FE Mock 모드 + 스트리밍
**목표:** BE 없이 단독 동작(정적 배포 데모).
- [ ] `mock/`(mode·store(localStorage)·sections·respond) + 데이터셋·DemoBadge. `isMock=!apiBase`·`?mock`.
- [ ] 시나리오 + 키워드 라우터(capability 미러·게이팅) → §2.1 봉투. 스트리밍(MockTransport delayMs).
- [ ] 커밋이 mock 스토어 반영(이력). ADR: FE mock 모드.
- **게이트:** jest(라우터·스토어·스트리밍) + 회귀(apiBase 시 미발동). **의존:** PR4(+PR7 계약).

## PR10 — FE 렌더 폴리시
- [ ] 신규 CTA/booking 템플릿 렌더·unhandled 구분(R7)·select_device 즉시 질의·레이턴시 인디케이터·analytics emit.
- **게이트:** jest. **의존:** PR9.

## PR11 — 아키텍처 문서 + 문서 탭 + README + Pages 배포
- [ ] `docs/{backend,bff,frontend}-architecture.md`·GH Pages **문서 탭**(`?screen=docs`).
- [ ] README(설치·실행·배포)·`deploy-pages.yml`(gh-pages).
- **게이트:** fe build + 배포. **의존:** PR1~PR10.

## (PR12) — 거버넌스
- [ ] LICENSE·SECURITY·CONTRIBUTING·CODE_OF_CONDUCT·dependabot·CODEOWNERS·PR/이슈 템플릿.

---

## 압축 매핑 (최소 8 PR)
1) PR1  · 2) PR2  · 3) PR3  · 4) PR4+PR5  · 5) PR6  · 6) PR7  · 7) PR8  · 8) PR9+PR10+PR11(+12).

## 비고
- 토글(`LLM_BACKED`·`MULTITENANT`·`PERSISTENCE`·`CAPABILITY_ORCH`)은 default-off로 각 PR이 회귀 없이 green.
- legacy/runtime(LLM prose)·실 RAG·관측 싱크 등은 본 시퀀스 이후의 **확장**(→ `docs/roadmap.md`).

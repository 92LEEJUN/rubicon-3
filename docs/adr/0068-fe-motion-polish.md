# ADR-0068: FE 모션·디자인 폴리시 = framer-motion 모션 레이어(웹 타깃) + 모션 토큰

- **상태**: 채택
- **관련**: [`specs/fe-motion-polish/`](../../specs/fe-motion-polish/requirements.md), [frontend-architecture.md §6](../frontend-architecture.md)(디자인 시스템/토큰), ADR-0023(FE 상태관리), ADR-0051(Mock 모드), R14(타이핑 인디케이터)
- **비고**: 0001~0067 사용 중 → 본 결정은 0068.

## 배경
FE는 토큰(`design/tokens.ts`)·프리미티브(`primitives.tsx`)는 탄탄하나 **전부 정적**이라 PoC처럼 읽힌다 —
등장/상태전환/누름 피드백에 모션이 없고(현재 `Animated`는 TypingDots·ChatPanel rise 2곳뿐), 카드가
1px 보더+옅은 그림자라 와이어프레임 같다. "동적 효과·디자인 디테일"로 완성도를 올리되, **검증 게이트
(jest jsdom·vite build)를 깨지 않고** 토큰처럼 일관되게 가야 한다.

핵심 사실: 이 앱의 **실제 타깃은 순수 웹**(vite, metro/expo 없음)이고 react-native-web은 컴포넌트
API일 뿐이다. jest도 `jsdom` + `react-native→react-native-web` 매핑으로 **DOM 렌더**를 검증한다.

## 결정
**모션을 디자인 시스템의 한 계층**으로 두고, 웹 모션 엔진으로 **framer-motion**을 채택한다.

- **모션 토큰** — `design/motion.ts`에 duration·easing·spring·거리(distance)·variants를 토큰화한다. 색을
  토큰화했듯 컴포넌트는 모션 토큰만 참조(하드코딩 금지) → 일관·교체 용이.
- **framer-motion ↔ RNW 통합** — `motion.create(View)`로 RN-Web 컴포넌트를 감싼다(검증 완료: jsdom에서
  정상 렌더). transform/opacity는 framer가 DOM 노드에 직접 적용하므로 RNW 스타일 처리와 충돌 없음.
- **모션 프리미티브** — `FadeInView`·`Stagger`/`StaggerItem`·`PressableScale`·`Skeleton`(시머)를 제공하고,
  `Card`·`Button`을 스프링 누름·elevation으로 폴리시한다.
- **접근성: reduced-motion 존중** — `prefers-reduced-motion`이면 모션을 0으로(즉시 표시). 모션은 **표현
  계층**이라 비활성에도 콘텐츠·기능 동일(회귀 불변).
- **톤: One UI 정제** — 현 토큰 위에서 깊이·여백·위계·미세 모션으로 "완성도"를 올린다(과한 연출 지양).

## 대안 / 기각
- **RN Animated 유지** — 의존성 0·이미 사용 중이나, 선언적 시퀀스·stagger·presence(exit) 표현이 번거롭고
  디테일 한계. 웹 단일 타깃이므로 이점 적음. **기각**(단, reduced-motion 폴백 등 단순 케이스엔 잔존 가능).
- **react-native-reanimated/Moti** — 네이티브+웹이나 babel 플러그인·RNW 호환 확인 부담. 네이티브 타깃이
  **없어** 이점이 안 살고 게이트 리스크만 큼. **기각**.
- **framer-motion(채택)** — 웹 한정 최고 표현력·선언적 variants·`AnimatePresence` exit·`prefers-reduced-motion`
  훅 내장. RNW 위 `motion.create` 통합·jsdom 렌더 **검증 완료**. 순수 웹 타깃과 정합.

## 영향
- **frontend-architecture.md §6** — 디자인 시스템에 **모션 레이어**(토큰·프리미티브·reduced-motion) 추가.
- **의존성** — `framer-motion`(웹 dependencies). 번들 영향은 build로 모니터(현 159KB gzip 기준).
- **게이트** — jest(jsdom)·vite build green 유지. 테스트는 **콘텐츠·접근성**을 검증(모션 타이밍 비검증).
- 구현·단계는 `specs/fe-motion-polish/design.md`·`tasks.md`. 토대→프리미티브→화면(채팅·홈)→전역 전환 순.

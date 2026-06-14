# 설계 (Design) — FE 모션·디자인 폴리시

> 요구사항 1~4 충족. 근거: [ADR-0068](../../docs/adr/0068-fe-motion-polish.md). 디자인 시스템은
> [frontend-architecture.md §6](../../docs/frontend-architecture.md), 톤=One UI 정제.

## 개요
모션을 디자인 시스템의 **한 계층**으로 추가한다: 토큰(`design/motion.ts`) → 프리미티브
(`components/motion.tsx`·`Skeleton.tsx`) → 프리미티브 폴리시(`Card`·`Button`) → 화면 적용(홈·채팅·
배너) → 전역 전환. 엔진은 framer-motion(`motion.create(View)`로 RNW 결합). reduced-motion 존중.

## 주요 컴포넌트 / 인터페이스
- **`design/motion.ts`** _(요구사항 1-1)_ — 토큰:
  - `duration`(fast 0.16·base 0.24·slow 0.36), `easing`(standard·decel·spring cubic-bezier),
  - `spring`(press·enter config), `distance`(sm 6·md 12), `variants`(fadeInUp·scaleIn·slideIn 등).
- **`components/motion.tsx`** _(요구사항 1-2)_:
  - `MotionView = motion.create(View)` — 공용 모션 래퍼.
  - `FadeInView` — 마운트 시 fadeInUp(거리·duration 토큰).
  - `Stagger`/`StaggerItem` — 부모가 자식 등장을 staggerChildren으로 순차화 _(요구사항 2-2)_.
  - `PressableScale` — `whileTap={{scale}}` 스프링 누름(RNW Pressable 위) _(요구사항 2-1)_.
  - `useReducedMotion()`(framer 내장) → 활성 시 모션 0 _(요구사항 4-1)_.
- **`components/Skeleton.tsx`** _(요구사항 3-1)_ — 시머 박스(opacity/translateX loop). `SkeletonCard` 헬퍼.
- **프리미티브 폴리시** _(요구사항 2-1·2-3)_ — `Card`(elevation 강화·optional press), `Button`(스프링 누름).
- **화면 적용**:
  - **홈**(`HomeScreen`) — 타일/추천 `Stagger` 등장 + `PressableScale`, 로딩 시 `SkeletonCard` _(요구사항 2·3-1)_.
  - **배너**(`ReEngagementBanner`) — `AnimatePresence` slide+fade enter/exit _(요구사항 3-2)_.
  - **채팅**(`StreamingMessage`) — 섹션 `FadeInView` 등장 _(요구사항 3-3)_.
  - **전역 전환**(후속 단계) — 탭/패널 open-close 트랜지션.

## 데이터 모델 / 계약
- **무변경** — 모션은 표현 계층. contract·라우팅·상태 흐름 불변 _(요구사항 4-3)_.

## 에러 처리 / 폴백
- framer 미가용/reduced-motion → 정적 렌더(콘텐츠 동일). 모션 실패가 렌더를 막지 않는다.

## 테스트 전략
- `tests/motion.test.tsx` — 프리미티브가 **자식 콘텐츠를 jsdom에서 렌더**(요구사항 1-3)·`PressableScale`
  onPress 동작·`Skeleton` 렌더·reduced-motion 경로. 모션 **타이밍은 비검증**(콘텐츠·접근성만, 요구사항 4-2).
- 기존 스위트 + `vite build` green 유지.

## 단계(스트랭글러)
1. 토대(토큰·프리미티브·Skeleton) + 프리미티브 폴리시 — **본 라운드**.
2. 홈·배너·채팅 섹션 적용 — **본 라운드(핵심 표면)**.
3. 전역 전환(탭/패널)·세부 디테일 패스 — 후속.

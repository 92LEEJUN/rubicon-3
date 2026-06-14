# 요구사항 (Requirements) — FE 모션·디자인 폴리시

## 개요
정적이라 PoC처럼 읽히는 FE에 **동적 효과(모션)와 디자인 디테일**을 더해 완성도를 올린다. 모션을 토큰화해
일관되게 깔고(framer-motion, ADR-0068), 프리미티브→화면 순으로 적용한다. **표현 계층**이므로 비활성
(reduced-motion)·테스트에서도 콘텐츠·기능은 동일해야 한다(회귀 불변). 톤은 **One UI 정제**.

## 요구사항 목록

### 요구사항 1: 모션 토큰·프리미티브 토대
**User Story:** 개발자로서, 색 토큰처럼 **모션도 한 곳에서** 일관되게 쓰기를 원한다.

**수용기준:**
1. WHEN 모션을 적용할 때 THEN 컴포넌트는 `design/motion.ts`의 **토큰**(duration·easing·spring·distance)만
   참조해야 한다 (SHALL). 하드코딩 금지.
2. WHEN 재사용 프리미티브(`FadeInView`·`Stagger`/`StaggerItem`·`PressableScale`·`Skeleton`)를 제공해야
   한다 (SHALL).
3. WHEN 이 프리미티브는 **jsdom(jest)에서 자식 콘텐츠를 정상 렌더**해야 한다 (SHALL, 게이트 불변).

### 요구사항 2: 마이크로 인터랙션·깊이
**User Story:** 사용자로서, 탭·등장이 부드럽고 표면에 깊이가 느껴지기를 원한다.

**수용기준:**
1. WHEN 카드/버튼/타일을 누를 때 THEN 시스템은 **스프링 스케일** 등 누름 피드백을 줘야 한다 (SHALL).
2. WHEN 리스트(홈 타일·추천)가 처음 나타날 때 THEN 항목은 **stagger fade/slide-in**으로 등장해야 한다 (SHALL).
3. WHEN 주요 표면(카드)은 **elevation/깊이**(그림자·여백·위계)를 일관되게 적용해야 한다 (SHALL).

### 요구사항 3: 상태 전환·로딩
**User Story:** 사용자로서, 로딩·배너·메시지 전환이 끊기지 않기를 원한다.

**수용기준:**
1. WHEN 데이터 로딩 중일 때 THEN 시스템은 빈 화면 대신 **Skeleton(시머)** 를 보여줄 수 있어야 한다 (SHALL).
2. WHEN 배너/메시지 섹션이 나타나거나 사라질 때 THEN **enter/exit 트랜지션**(slide+fade)을 적용해야 한다
   (SHALL, `AnimatePresence`).
3. WHEN 채팅 섹션이 스트리밍으로 도착할 때 THEN 각 섹션은 **부드럽게 등장**해야 한다 (SHALL).

### 요구사항 4: 접근성·회귀 불변
**수용기준:**
1. IF `prefers-reduced-motion`이면 THEN 시스템은 모션을 비활성(즉시 표시)하되 콘텐츠·기능은 **동일**해야
   한다 (SHALL).
2. WHEN 기존 jest(jsdom)·vite build 게이트는 **green을 유지**해야 한다 (SHALL). 테스트는 콘텐츠·접근성을
   검증하고 모션 타이밍은 검증하지 않는다.
3. WHEN 모션은 **표현만** 바꾸고 데이터 흐름·계약(contract)·라우팅은 바꾸지 않아야 한다 (SHALL).

/**
 * 모션 토큰 — 색 토큰처럼 **한 곳에서** 일관되게(ADR-0068, frontend-architecture §6).
 * 컴포넌트는 이 토큰만 참조한다(하드코딩 금지). 엔진은 framer-motion(웹 타깃).
 * 톤: One UI 정제 — 짧고 부드러운 decel 곡선, 절제된 거리·스프링.
 */

// 지속시간(초) — framer 단위.
export const duration = { fast: 0.16, base: 0.24, slow: 0.36 } as const;

// 이징 — cubic-bezier 4튜플(One UI standard/decelerate).
export const easing = {
  standard: [0.4, 0, 0.2, 1] as [number, number, number, number],
  decel: [0, 0, 0.2, 1] as [number, number, number, number],
  accel: [0.4, 0, 1, 1] as [number, number, number, number],
} as const;

// 스프링 — 누름/등장 물성.
export const spring = {
  press: { type: 'spring', stiffness: 420, damping: 28, mass: 0.6 },
  enter: { type: 'spring', stiffness: 260, damping: 24 },
} as const;

// 이동 거리(px) — 절제된 슬라이드.
export const distance = { sm: 6, md: 12 } as const;

// ── variants (framer) ──────────────────────────────────────────────────────
export const fadeInUp = {
  hidden: { opacity: 0, y: distance.md },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: duration.base, ease: easing.decel },
  },
} as const;

export const scaleIn = {
  hidden: { opacity: 0, scale: 0.96 },
  show: { opacity: 1, scale: 1, transition: { duration: duration.base, ease: easing.decel } },
} as const;

export const slideInDown = {
  hidden: { opacity: 0, y: -distance.md },
  show: { opacity: 1, y: 0, transition: { duration: duration.base, ease: easing.decel } },
  exit: { opacity: 0, y: -distance.sm, transition: { duration: duration.fast, ease: easing.accel } },
} as const;

/** 부모 stagger — 자식(StaggerItem)을 순차 등장시킨다. */
export const staggerParent = (stagger = 0.06) =>
  ({
    hidden: {},
    show: { transition: { staggerChildren: stagger, delayChildren: 0.02 } },
  }) as const;

// 누름 피드백(whileTap)·호버(whileHover).
export const pressTap = { scale: 0.97 } as const;
export const hoverLift = { y: -2 } as const;

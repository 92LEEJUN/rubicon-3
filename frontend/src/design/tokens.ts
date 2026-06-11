/**
 * 디자인 토큰 — Samsung One UI 스타일(frontend-architecture.md §6).
 * 컴포넌트는 토큰만 참조(하드코딩 금지). 디자이너 애셋 도착 시 값만 교체.
 */
export const color = {
  // One UI 블루 계열
  primary: "#0381FE",
  primaryDark: "#026AD6",
  primaryTint: "#E8F2FF",
  // 중립
  bg: "#F5F6F8",
  surface: "#FFFFFF",
  surfaceAlt: "#F0F2F5",
  border: "#E3E6EB",
  text: "#1A1C1E",
  textSub: "#5A6068",
  textMuted: "#8B9097",
  // 상태
  success: "#1FA463",
  warning: "#F2A20C",
  danger: "#E5484D",
  successTint: "#E6F6EE",
  warningTint: "#FDF3E0",
  dangerTint: "#FCEBEC",
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { sm: 8, md: 12, lg: 18, xl: 26, pill: 999 } as const;

export const font = {
  size: { xs: 12, sm: 13, md: 15, lg: 17, xl: 20, xxl: 26 },
  weight: { regular: "400", medium: "500", semibold: "600", bold: "700" },
} as const;

export const shadow = {
  card: {
    shadowColor: "#000",
    shadowOpacity: 0.06,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
} as const;

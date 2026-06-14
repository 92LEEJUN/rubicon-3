/**
 * 디자인 토큰 — **토스(Toss)st 정제 미니멀**(ADR-0068, frontend-architecture §6).
 * 컴포넌트는 토큰만 참조(하드코딩 금지). 키는 유지하고 값만 토스 결로 교체 → 전 화면 일괄 반영.
 * 특징: 화이트 표면·토스 블루 단일 액센트·그레이 스케일·큰 볼드 타이포·아주 부드러운 섀도우.
 */
export const color = {
  // Toss Blue — 단일 강한 액센트
  primary: '#3182F6',
  primaryDark: '#1B64DA',
  primaryTint: '#E8F2FE',
  // 표면 — 화이트 중심 + 토스 그레이
  bg: '#FFFFFF',
  surface: '#FFFFFF',
  surfaceAlt: '#F2F4F6',
  border: '#E5E8EB',
  // 텍스트 — 토스 그레이 스케일
  text: '#191F28',
  textSub: '#4E5968',
  textMuted: '#8B95A1',
  // 상태
  success: '#0AB26B',
  warning: '#FF8A00',
  danger: '#F04452',
  successTint: '#E7F8F0',
  warningTint: '#FFF4E5',
  dangerTint: '#FEECEE',
} as const;

// 여백 — 토스는 넉넉하다. 큰 단위(xxxl) 추가.
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 44 } as const;

// 라운드 — 소프트한 카드(16~20)·버튼(14).
export const radius = { sm: 8, md: 12, lg: 16, xl: 20, pill: 999 } as const;

export const font = {
  // 전역 강제(index.html)와 일치 — 직접 참조가 필요한 곳을 위해 토큰으로도 노출.
  family:
    "'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
  // 토스는 위계가 크다 — display(큰 인사/숫자) 추가, 전반적으로 한 단계 키움.
  size: { xs: 12, sm: 13, md: 15, lg: 17, xl: 20, xxl: 26, display: 32 },
  weight: { regular: '400', medium: '500', semibold: '600', bold: '700', heavy: '800' },
} as const;

// 브랜드 그라데이션 — 토스 블루 결.
export const gradient = {
  brand: 'linear-gradient(135deg, #4593FC 0%, #3182F6 100%)',
} as const;

// 섀도우 — 토스는 거의 평평하고 아주 부드럽다(보더 대신 옅은 그림자로 분리).
export const shadow = {
  card: {
    shadowColor: '#191F28',
    shadowOpacity: 0.04,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 2,
  },
  elevated: {
    shadowColor: '#191F28',
    shadowOpacity: 0.08,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 10 },
    elevation: 6,
  },
} as const;

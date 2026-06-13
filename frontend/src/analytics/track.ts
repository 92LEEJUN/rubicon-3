/**
 * 분석 트래킹(최소 구현) — docs/analytics.md §4 택소노미의 이벤트명을 사용한다.
 *
 * 상태: FE→BFF/BE 싱크는 후속(deferred, analytics.md §본문). 여기서는 가벼운 클라이언트
 * 유틸만 둔다 — 기본 싱크는 console(개발 가시성), 프로덕션은 no-op이 되도록 교체 가능.
 * 이벤트명은 `object_action`(과거형) 규칙(§2)을 따른다.
 */

/** docs/analytics.md §4 카탈로그의 FE-소유 이벤트명(알려진 값 열거 — permissive). */
export type AnalyticsEventName =
  | 'screen_viewed'
  | 'screen_exited'
  | 'chat_opened'
  | 'card_tapped'
  | 'message_sent' // 턴 전송(인게이지먼트 시작, §5)
  | 'template_shown'
  | 'cta_shown'
  | 'cta_clicked' // CTA 탭(기여 시작)
  | 'checkout_shown'
  | 'resolution_confirmed'
  | 'fallback_shown'
  | 'error_shown'
  | 'notification_opened'
  | 'notification_dismissed'
  // order_confirmed의 owner는 BE이나, FE 데모/오프라인(BE 미연결) 경로의 커밋 확정도
  // 가시화하기 위해 클라 사이드에서 같은 이름으로 발행한다(실 연동 시 BE가 진실의 출처).
  | 'order_confirmed';

export type AnalyticsProps = Record<string, unknown>;

export type AnalyticsSink = (name: string, props?: AnalyticsProps) => void;

/** 기본 싱크 — 개발 중 console, 그 외 no-op(비차단). BFF/BE 싱크는 후속. */
const consoleSink: AnalyticsSink = (name, props) => {
  // eslint-disable-next-line no-console
  if (typeof console !== 'undefined' && console.debug)
    console.debug('[analytics]', name, props ?? {});
};

let sink: AnalyticsSink = consoleSink;

/** 싱크 교체(테스트·실 연동 시). */
export function setAnalyticsSink(next: AnalyticsSink | null): void {
  sink = next ?? (() => {});
}

export interface AnalyticsConfig {
  /** BFF 베이스 URL(api.ts의 ApiConfig.base와 동일). 없으면 mock/no-base → console. */
  base?: string;
  /** 로그인 토큰(있으면 Authorization 헤더로 BFF가 principal 태깅). */
  token?: string;
  /** 이벤트 수신 경로. 기본 BFF 라우트. */
  path?: string;
}

/**
 * BFF 싱크 — 설정된 base가 있으면 이벤트를 BFF로 fire-and-forget POST.
 * 비차단: 응답을 기다리지 않고, 모든 에러는 삼킨다(분석은 UX를 막지 않음).
 */
export function bffSink(cfg: AnalyticsConfig): AnalyticsSink {
  const url = (cfg.base ?? '') + (cfg.path ?? '/internal/events');
  return (name, props) => {
    try {
      void fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(cfg.token ? { Authorization: `Bearer ${cfg.token}` } : {}),
        },
        body: JSON.stringify({ name, props: props ?? {}, ts: Date.now() / 1000 }),
        keepalive: true, // 페이지 이탈 중에도 전송(언로드 안전)
      }).catch(() => {
        /* 네트워크 실패 무시(비차단) */
      });
    } catch {
      /* fetch 미지원/동기 throw 무시 */
    }
  };
}

/**
 * 분석 싱크 배선 — base가 있으면 BFF 싱크, 없으면(mock/정적 배포) console 폴백.
 * 앱 부트스트랩(main.tsx)에서 apiBase와 함께 1회 호출하는 것을 의도(현재는 옵셔널).
 */
export function configureAnalytics(cfg: AnalyticsConfig): void {
  setAnalyticsSink(cfg.base ? bffSink(cfg) : consoleSink);
}

/**
 * track(event, props?) — 이벤트 1건 발행. 비차단(실패 무시).
 * 배선 지점: 턴 전송(message_sent), CTA 탭(cta_clicked), 커밋 확정(order_confirmed).
 */
export function track(name: AnalyticsEventName | string, props?: AnalyticsProps): void {
  try {
    sink(name, props);
  } catch {
    /* 분석은 절대 UX를 막지 않는다 */
  }
}

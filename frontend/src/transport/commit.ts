/**
 * 커밋 라운드트립(REST) — 주문/예약 확정 게이트(SHARED CONTRACT §commit).
 *
 * commit CTA(kind ∈ {order, booking}, action:"commit") → REST commit 엔드포인트 호출.
 *  - 409 {code:"ConfirmationRequired", template:{kind:"confirmation"}}
 *      → 확인 템플릿을 노출하고, 사용자가 확정하면 confirmed:true로 재-POST(2-step).
 *  - 401 {code:"LoginRequired", cta:{kind:"login"}}
 *      → 로그인 월 노출(게스트는 commit만 게이트, advisory는 통과).
 *  - 그 외 2xx → 성공(주문/예약 확정).
 * apiBase 미설정(정적 배포)이면 네트워크를 타지 않고 데모 확정으로 정규화한다.
 */
import type { ApiConfig } from './api';
import type { Cta, Template } from '../types/contract';
import { mockStore } from '../mock/store';
import { PARTS, PRODUCTS } from '../fixtures/mockData';

/** commit 대상 종류(엔드포인트 매핑). */
export type CommitKind = 'order' | 'booking';

/** commit 결과(호출 훅이 분기). */
export type CommitResult =
  | { status: 'ok'; data?: any } // 확정됨
  | { status: 'confirm'; template: Template; payload: Record<string, unknown> } // 409 — 확인 필요(재제출용 payload 동봉)
  | { status: 'login'; cta?: Cta } // 401 — 로그인 필요
  | { status: 'error'; code?: string }; // 그 외 실패

const PATH: Record<CommitKind, string> = {
  order: '/orders', // BFF POST /orders (→ BE /internal/orders, 409/401 게이트)
  booking: '/bookings', // BFF POST /bookings (→ BE /internal/bookings)
};

function headers(cfg: ApiConfig): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...(cfg.token ? { Authorization: `Bearer ${cfg.token}` } : {}),
  };
}

function commitKindOf(cta: Cta): CommitKind | null {
  if (cta.action !== 'commit') return null;
  if (cta.kind === 'order' || cta.kind === 'booking') return cta.kind;
  return null;
}

/** 이 CTA가 REST commit 라운드트립 대상인지(order/booking commit). */
export function isCommitCta(cta: Cta): boolean {
  return commitKindOf(cta) !== null;
}

/**
 * commit 1회 호출. `confirmed`는 2-step 재제출 시 true.
 * payload = CTA payload + {confirmed?}. 호출 측은 status에 따라 confirm/login/ok를 분기한다.
 */
export async function commit(
  cfg: ApiConfig,
  kind: CommitKind,
  payload: Record<string, unknown>,
  confirmed = false,
): Promise<CommitResult> {
  const body = { ...payload, ...(confirmed ? { confirmed: true } : {}) };

  // 정적 배포(BE 미연결) — 데모 모드. 미확정 첫 호출은 확인 게이트를, 확정 후엔 성공을 흉내낸다.
  if (!cfg.base) {
    if (!confirmed) {
      return { status: 'confirm', template: demoConfirmation(kind), payload: body };
    }
    return { status: 'ok', data: { committed: true, demo: true, ...recordDemoCommit(kind, body) } };
  }

  try {
    const r = await fetch(cfg.base + PATH[kind], {
      method: 'POST',
      headers: headers(cfg),
      body: JSON.stringify(body),
    });

    if (r.status === 409) {
      const j = await r.json().catch(() => ({}) as any);
      // {code:"ConfirmationRequired", template:{kind:"confirmation"}}
      return {
        status: 'confirm',
        template: (j?.template as Template) ?? demoConfirmation(kind),
        payload: body,
      };
    }
    if (r.status === 401) {
      const j = await r.json().catch(() => ({}) as any);
      // {code:"LoginRequired", cta:{kind:"login"}}
      return {
        status: 'login',
        cta: (j?.cta as Cta) ?? { label: '로그인', action: 'navigate', kind: 'login' },
      };
    }
    if (!r.ok) {
      const j = await r.json().catch(() => ({}) as any);
      return { status: 'error', code: j?.code };
    }
    const data = await r.json().catch(() => undefined);
    return { status: 'ok', data };
  } catch {
    return { status: 'error' };
  }
}

/**
 * commitFromCta — CTA에서 kind/payload를 추출해 commit 호출.
 * commit 대상이 아니면 null(호출 측이 일반 chat 후속으로 라우팅).
 */
export async function commitFromCta(
  cfg: ApiConfig,
  cta: Cta,
  confirmed = false,
): Promise<CommitResult | null> {
  const kind = commitKindOf(cta);
  if (!kind) return null;
  return commit(cfg, kind, (cta.payload as Record<string, unknown>) ?? {}, confirmed);
}

/** 데모 모드 — 확정 커밋을 mock 스토어에 기록(주문/예약 이력에 반영, ADR-0051). */
function recordDemoCommit(
  kind: CommitKind,
  body: Record<string, unknown>,
): Record<string, unknown> {
  if (kind === 'booking') {
    const bk = mockStore.addBooking(
      String(body.slot_id ?? 'slot_1'),
      String(body.visit_type ?? 'REPAIR'),
    );
    return { booking_id: bk.id };
  }
  const partIds = (body.part_ids as string[]) ?? [];
  const prodIds = (body.product_ids as string[]) ?? [];
  const items = [
    ...partIds.map((pid) => ({
      part_id: pid,
      name: PARTS[pid]?.name ?? pid,
      price: PARTS[pid]?.price ?? 0,
    })),
    ...prodIds.map((pid) => {
      const p = PRODUCTS.find((x) => x.id === pid);
      return { part_id: pid, name: p?.name ?? pid, price: p?.price ?? 0 };
    }),
  ];
  const ord = mockStore.addOrder(
    items.length
      ? items
      : [
          {
            part_id: 'part_drain_filter',
            name: PARTS.part_drain_filter.name,
            price: PARTS.part_drain_filter.price,
          },
        ],
  );
  return { order_id: ord.id };
}

/** 데모/폴백 확인 템플릿 — BE가 confirmation 템플릿을 안 줄 때. */
function demoConfirmation(kind: CommitKind): Template {
  if (kind === 'booking') {
    return {
      kind: 'confirmation',
      data: {
        message: '방문 예약을 확정할까요? 선택한 시간으로 기사 방문이 예약됩니다.',
        booking: true,
      },
    };
  }
  return {
    kind: 'confirmation',
    data: {
      order: { status: 'DRAFT' },
      summary: { subtotal: 0, total: 0 },
      message: '주문을 확정할까요? 결제 후에는 되돌릴 수 없어요.',
    },
  };
}

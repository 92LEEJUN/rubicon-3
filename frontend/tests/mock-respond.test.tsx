/** Mock 채팅 라우터(ADR-0051) — 시나리오/키워드 분기·게이팅·봉투. */
import { respond } from '../src/mock/respond';
import { mockStore } from '../src/mock/store';
import type { MessageSection } from '../src/types/contract';

beforeEach(() => mockStore.reset());

const sectionsOf = (chunks: ReturnType<typeof respond>): MessageSection[] =>
  chunks.filter((c) => c.type === 'section').map((c: any) => c.section);

test('봉투 순서 — delta → section* → flow → done', () => {
  const ch = respond('세탁기 물이 안 빠져요');
  expect(ch[0].type).toBe('delta');
  expect(ch[ch.length - 1].type).toBe('done');
  expect(ch.some((c) => c.type === 'flow')).toBe(true);
});

test('진단 — guide_steps + flow=troubleshoot', () => {
  const ch = respond('세탁기 물이 안 빠져요 5C');
  const secs = sectionsOf(ch);
  expect(secs.some((s) => s.template.kind === 'guide_steps')).toBe(true);
  expect(ch.find((c) => c.type === 'flow')).toMatchObject({ active_flow: 'troubleshoot' });
});

test('안전 위험 — cta_notice + 부품 주문 CTA 숨김', () => {
  const sec = sectionsOf(respond('인덕션에서 타는 냄새가 나요'))[0];
  expect(sec.template.data.cta_notice).toBeTruthy();
  expect(sec.ctas.map((c) => c.kind)).not.toContain('order');
  expect(sec.ctas.map((c) => c.kind)).toEqual(expect.arrayContaining(['handoff', 'booking']));
});

test('주문 — 재고 product_card / 품절 unhandled', () => {
  const stock = sectionsOf(respond('정수필터 주문해줘')).find((s) => s.intent === 'order')!;
  expect(stock.handled).toBe(true);
  expect(stock.template.kind).toBe('product_card');
  const oos = sectionsOf(respond('헤파 필터 주문해줘')).find((s) => s.intent === 'order')!;
  expect(oos.handled).toBe(false);
});

test('보증·예약 — F2 라우팅', () => {
  expect(sectionsOf(respond('보증으로 무상 수리 되나요 기사 예약도')).map((s) => s.intent)).toEqual(
    expect.arrayContaining(['warranty', 'booking']),
  );
});

test('추천 → candidates 기록, 이후 explain이 사용', () => {
  respond('공기청정기 추천해줘');
  expect(mockStore.getCandidates().length).toBeGreaterThan(0);
  const ex = sectionsOf(respond('더 알려줘'))[0];
  expect(ex.intent).toBe('explain');
  expect(ex.template.data.products.length).toBeGreaterThan(0);
});

test('모호 입력 → clarify', () => {
  expect(sectionsOf(respond('음'))[0].intent).toBe('clarify');
});

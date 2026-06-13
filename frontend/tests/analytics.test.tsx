/**
 * 분석 싱크 배선(docs/analytics.md §4) — FE track() → BFF /internal/events.
 *
 * 검증:
 * - configureAnalytics({base}) → track 가 BFF로 fire-and-forget POST(이름·props 본문).
 * - 에러 삼킴: fetch 가 reject/throw 해도 track 은 던지지 않는다(비차단).
 * - 콘솔 폴백: base 없으면(mock/정적) console.debug 로 떨어지고 fetch 는 안 친다.
 */
import { track, configureAnalytics, setAnalyticsSink } from '../src/analytics/track';

afterEach(() => {
  delete (global as any).fetch;
  setAnalyticsSink(null); // 다른 테스트로 싱크가 새지 않도록 no-op 복구
  jest.restoreAllMocks();
});

test('configured base — track 가 BFF /internal/events 로 POST(이름·props 본문)', () => {
  const fetchMock = jest.fn(() => Promise.resolve({ ok: true } as any));
  (global as any).fetch = fetchMock;

  configureAnalytics({ base: 'http://bff', token: 'tok' });
  track('message_sent', { modality: 'text' });

  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [url, init] = fetchMock.mock.calls[0] as [string, any];
  expect(url).toBe('http://bff/internal/events');
  expect(init.method).toBe('POST');
  expect(init.headers.Authorization).toBe('Bearer tok');
  const body = JSON.parse(init.body);
  expect(body.name).toBe('message_sent');
  expect(body.props).toEqual({ modality: 'text' });
  expect(typeof body.ts).toBe('number');
});

test('custom path 존중', () => {
  const fetchMock = jest.fn(() => Promise.resolve({ ok: true } as any));
  (global as any).fetch = fetchMock;
  configureAnalytics({ base: 'http://bff', path: '/x/events' });
  track('cta_clicked');
  expect((fetchMock.mock.calls[0] as any)[0]).toBe('http://bff/x/events');
});

test('에러 삼킴 — fetch 가 reject 해도 track 은 던지지 않는다(비차단)', () => {
  const fetchMock = jest.fn(() => Promise.reject(new Error('network down')));
  (global as any).fetch = fetchMock;
  configureAnalytics({ base: 'http://bff' });
  expect(() => track('order_confirmed')).not.toThrow();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test('에러 삼킴 — fetch 가 동기 throw 해도 track 은 던지지 않는다', () => {
  (global as any).fetch = jest.fn(() => {
    throw new Error('sync boom');
  });
  configureAnalytics({ base: 'http://bff' });
  expect(() => track('error_shown', { code: 'x' })).not.toThrow();
});

test('콘솔 폴백 — base 없으면 fetch 안 치고 console.debug 로 떨어짐', () => {
  const fetchMock = jest.fn();
  (global as any).fetch = fetchMock;
  const debug = jest.spyOn(console, 'debug').mockImplementation(() => {});

  configureAnalytics({}); // base 없음 → mock/정적 배포 경로

  track('screen_viewed', { name: 'home' });
  expect(fetchMock).not.toHaveBeenCalled();
  expect(debug).toHaveBeenCalledWith('[analytics]', 'screen_viewed', { name: 'home' });
});

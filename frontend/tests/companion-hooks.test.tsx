/** 컴패니언 훅 — useOpenLoops·useResume·useReEngagement(요구 1·2·3·5·6). */
import React from 'react';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useOpenLoops } from '../src/state/useOpenLoops';
import { useResume } from '../src/state/useResume';
import { useReEngagement } from '../src/state/useReEngagement';
import { ConsentProvider, createConsentStore } from '../src/state/useConsent';
import { companionStore } from '../src/state/companionStore';
import type { OpenLoop } from '../src/types/contract';

const cfg = { base: 'https://bff.test', token: 't' };

function mockFetch(
  impl: (url: string, init?: any) => { status?: number; ok?: boolean; json?: () => any },
) {
  (global as any).fetch = jest.fn((url: string, init?: any) => {
    const r = impl(String(url), init);
    return Promise.resolve({
      ok: r.ok ?? (r.status ? r.status < 400 : true),
      status: r.status ?? 200,
      json: async () => (r.json ? r.json() : {}),
    });
  });
}

afterEach(() => {
  delete (global as any).fetch;
  companionStore.reset();
});

const loops: OpenLoop[] = [
  { id: '1', kind: 'issue', ref: 'i1', status: 'open', priority: 5, summary: '세탁기 5C' },
  { id: '2', kind: 'order', ref: 'o1', status: 'open', priority: 1, summary: '필터 주문' },
];

// ── useOpenLoops ──────────────────────────────────────────────
test('useOpenLoops — resolve 성공 시 낙관적 제거 유지(요구 2.4)', async () => {
  mockFetch(() => ({ status: 200, json: () => ({ id: '1' }) }));
  const { result } = renderHook(() => useOpenLoops(cfg, loops));
  expect(result.current.loops).toHaveLength(2);
  await act(async () => {
    await result.current.resolve('i1');
  });
  expect(result.current.loops.map((l) => l.ref)).toEqual(['o1']);
  expect(result.current.error).toBeNull();
});

test('useOpenLoops — 404면 롤백 + 에러 안내(요구 2.5)', async () => {
  mockFetch(() => ({ status: 404 }));
  const { result } = renderHook(() => useOpenLoops(cfg, loops));
  await act(async () => {
    await result.current.dismiss('i1');
  });
  // 롤백 → 항목 복원
  expect(result.current.loops.map((l) => l.ref).sort()).toEqual(['i1', 'o1']);
  expect(result.current.error).toMatch(/이미 처리/);
});

// ── useResume ─────────────────────────────────────────────────
function consentWrapper(optedIn: boolean) {
  const store = createConsentStore({ opted_in: optedIn });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <ConsentProvider store={store}>{children}</ConsentProvider>
  );
  return { Wrapper, store };
}

test('useResume — has_context=false면 카드 미표시(요구 1.6)', async () => {
  mockFetch(() => ({ json: () => ({ has_context: false }) }));
  const { Wrapper } = consentWrapper(true);
  const { result } = renderHook(() => useResume(cfg, true), { wrapper: Wrapper });
  await waitFor(() => expect(result.current.status).toBe('success'));
  expect(result.current.hasContext).toBe(false);
});

test('useResume — 미동의면 개인화 요약 비노출(요구 6.2)', async () => {
  mockFetch(() => ({
    json: () => ({
      has_context: true,
      personalized: true,
      summary: '개인화 요약',
      open_loops: loops,
    }),
  }));
  const { Wrapper } = consentWrapper(false);
  const { result } = renderHook(() => useResume(cfg, true), { wrapper: Wrapper });
  await waitFor(() => expect(result.current.status).toBe('success'));
  // 개인화 요약은 제거되지만 미해결 목록(중립)은 남는다
  expect(result.current.resume?.summary).toBeUndefined();
  expect(result.current.resume?.open_loops).toHaveLength(2);
});

test('useResume — 동의 시 개인화 요약 노출(요구 6)', async () => {
  mockFetch(() => ({
    json: () => ({ has_context: true, personalized: true, summary: '개인화 요약' }),
  }));
  const { Wrapper } = consentWrapper(true);
  const { result } = renderHook(() => useResume(cfg, true), { wrapper: Wrapper });
  await waitFor(() => expect(result.current.status).toBe('success'));
  expect(result.current.resume?.summary).toBe('개인화 요약');
  expect(result.current.hasContext).toBe(true);
});

test('useResume — startFresh는 resume 가시성을 dismissed로(요구 1.5)', async () => {
  mockFetch(() => ({ json: () => ({ has_context: true, summary: '요약' }) }));
  const { Wrapper } = consentWrapper(true);
  const { result } = renderHook(() => useResume(cfg, true), { wrapper: Wrapper });
  await waitFor(() => expect(result.current.hasContext).toBe(true));
  act(() => {
    result.current.startFresh();
  });
  expect(companionStore.get().resumeVisibility).toBe('dismissed');
  expect(result.current.hasContext).toBe(false);
});

// ── useReEngagement ───────────────────────────────────────────
test('useReEngagement — 미동의면 조회 자체를 안 한다(게이트, 요구 6.1)', async () => {
  mockFetch(() => ({ json: () => ({ primary_label: '부품 입고' }) }));
  const { Wrapper } = consentWrapper(false);
  const { result } = renderHook(() => useReEngagement(cfg, true), { wrapper: Wrapper });
  await act(async () => {
    await Promise.resolve();
  });
  expect((global as any).fetch).not.toHaveBeenCalled();
  expect(result.current.banner).toBeNull();
});

test('useReEngagement — 동의 시 deliver로 조회·노출(요구 3.1·3.2)', async () => {
  let method = '';
  mockFetch((_u, init) => {
    method = init?.method;
    return { json: () => ({ primary_label: '부품 입고', primary_ref: 'r1' }) };
  });
  const { Wrapper } = consentWrapper(true);
  const { result } = renderHook(() => useReEngagement(cfg, true), { wrapper: Wrapper });
  await waitFor(() => expect(result.current.banner).not.toBeNull());
  expect(method).toBe('POST'); // deliver 확정
  expect(result.current.primaryRef).toBe('r1');
});

test('useReEngagement — {}면 미노출(요구 3.4)', async () => {
  mockFetch(() => ({ json: () => ({}) }));
  const { Wrapper } = consentWrapper(true);
  const { result } = renderHook(() => useReEngagement(cfg, true), { wrapper: Wrapper });
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(result.current.banner).toBeNull();
});

test('useReEngagement — dismiss 후 미노출(요구 3.5)', async () => {
  mockFetch(() => ({ json: () => ({ primary_label: '부품 입고' }) }));
  const { Wrapper } = consentWrapper(true);
  const { result } = renderHook(() => useReEngagement(cfg, true), { wrapper: Wrapper });
  await waitFor(() => expect(result.current.banner).not.toBeNull());
  act(() => {
    result.current.dismiss();
  });
  expect(result.current.banner).toBeNull();
  expect(companionStore.get().bannerState).toBe('dismissed');
});

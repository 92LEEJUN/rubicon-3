/** useVariant 훅(S8, ADR-0064) — 우선순위 폴백·노출 발행·de-dup. */
import { renderHook } from '@testing-library/react';

import * as trackMod from '../analytics/track';
import { ExperimentDef } from './client';
import { resolveVariant, useVariant } from './useVariant';

const def: ExperimentDef = {
  key: 'exp_a',
  variants: [
    { name: 'control', weight: 1 },
    { name: 'treatment', weight: 1 },
  ],
  control: 'control',
  salt: 'exp_a',
};

describe('resolveVariant', () => {
  it('주입된 assignment 맵이 최우선', () => {
    expect(resolveVariant('exp_a', { assignments: { exp_a: 'treatment' }, def, unit: 'u1' })).toBe(
      'treatment',
    );
  });
  it('맵 없으면 로컬 def 해시', () => {
    expect(['control', 'treatment']).toContain(resolveVariant('exp_a', { def, unit: 'u1' }));
  });
  it('def·맵 모두 없으면 control', () => {
    expect(resolveVariant('exp_a', {})).toBe('control');
  });
});

describe('useVariant', () => {
  beforeEach(() => jest.restoreAllMocks());

  it('control이 아니면 노출(experiment_exposed)을 1회 발행', () => {
    const spy = jest.spyOn(trackMod, 'track').mockImplementation(() => {});
    const { rerender } = renderHook(() =>
      useVariant('exp_a', { assignments: { exp_a: 'treatment' } }),
    );
    rerender();
    rerender();
    const calls = spy.mock.calls.filter((c) => c[0] === 'experiment_exposed');
    expect(calls.length).toBe(1);
    expect(calls[0][1]).toEqual({ experiment: 'exp_a', variant: 'treatment' });
  });

  it('control이면 노출하지 않음', () => {
    const spy = jest.spyOn(trackMod, 'track').mockImplementation(() => {});
    renderHook(() => useVariant('exp_a', { assignments: { exp_a: 'control' } }));
    expect(spy.mock.calls.filter((c) => c[0] === 'experiment_exposed').length).toBe(0);
  });

  it('expose=false면 노출하지 않음', () => {
    const spy = jest.spyOn(trackMod, 'track').mockImplementation(() => {});
    renderHook(() => useVariant('exp_a', { assignments: { exp_a: 'treatment' }, expose: false }));
    expect(spy.mock.calls.filter((c) => c[0] === 'experiment_exposed').length).toBe(0);
  });

  it('미해결이면 control 반환', () => {
    const { result } = renderHook(() => useVariant('exp_a', {}));
    expect(result.current).toBe('control');
  });
});

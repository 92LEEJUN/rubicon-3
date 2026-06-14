/** 실험 클라이언트(S8, ADR-0064) — assignLocal 결정성·분포·canary/홀드아웃·폴백. */
import { assignLocal, bucket, ExperimentDef } from './client';

const exp = (over: Partial<ExperimentDef> = {}): ExperimentDef => ({
  key: 'exp_a',
  variants: [
    { name: 'control', weight: 1 },
    { name: 'treatment', weight: 1 },
  ],
  control: 'control',
  rollout: 1,
  holdout: 0,
  salt: 'exp_a',
  ...over,
});

describe('bucket', () => {
  it('같은 입력은 같은 값(결정적)', () => {
    expect(bucket('s', 'k', 'u1')).toBe(bucket('s', 'k', 'u1'));
  });
  it('값은 [0,1) 범위', () => {
    for (let i = 0; i < 50; i++) {
      const b = bucket('s', 'k', `u${i}`);
      expect(b).toBeGreaterThanOrEqual(0);
      expect(b).toBeLessThan(1);
    }
  });
});

describe('assignLocal', () => {
  it('def 없으면 control', () => {
    expect(assignLocal(null, 'u1')).toBe('control');
  });
  it('unit 없으면 control', () => {
    expect(assignLocal(exp(), null)).toBe('control');
    expect(assignLocal(exp(), '')).toBe('control');
  });
  it('sticky — 같은 unit은 항상 같은 variant', () => {
    const a = assignLocal(exp(), 'user-7');
    const b = assignLocal(exp(), 'user-7');
    expect(a).toBe(b);
    expect(['control', 'treatment']).toContain(a);
  });
  it('가중치 분포 근사(75/25)', () => {
    const e = exp({
      variants: [
        { name: 'control', weight: 3 },
        { name: 'treatment', weight: 1 },
      ],
    });
    const n = 4000;
    let treat = 0;
    for (let i = 0; i < n; i++) if (assignLocal(e, `u${i}`) === 'treatment') treat++;
    const frac = treat / n;
    expect(frac).toBeGreaterThan(0.18);
    expect(frac).toBeLessThan(0.32);
  });
  it('rollout=0 → 전원 control', () => {
    const e = exp({ rollout: 0 });
    for (let i = 0; i < 100; i++) expect(assignLocal(e, `u${i}`)).toBe('control');
  });
  it('holdout=1 → 전원 control', () => {
    const e = exp({ holdout: 1, variants: [{ name: 'treatment', weight: 1 }] });
    for (let i = 0; i < 100; i++) expect(assignLocal(e, `u${i}`)).toBe('control');
  });
  it('rollout 부분 — 일부만 실험 대상', () => {
    const e = exp({ rollout: 0.5, variants: [{ name: 'treatment', weight: 1 }] });
    const n = 2000;
    let treat = 0;
    for (let i = 0; i < n; i++) if (assignLocal(e, `u${i}`) === 'treatment') treat++;
    const frac = treat / n;
    expect(frac).toBeGreaterThan(0.4);
    expect(frac).toBeLessThan(0.6);
  });
});

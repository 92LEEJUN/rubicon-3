/**
 * useVariant 훅(S8, ADR-0064) — 실험 variant를 읽고 노출을 1회 발행한다.
 *
 * 우선순위(요구사항 4.2):
 *   1) 주입된 assignment 맵(BE 권위 결과를 상위에서 fetch해 내려줌)
 *   2) 로컬 def 결정적 해시(오프라인/mock 폴백)
 *   3) control
 * 노출: variant가 control이 아니면 `track('experiment_exposed', {experiment, variant})`를
 * 컴포넌트 마운트 시 1회 발행(append-only 택소노미). 토글 권위는 BE — FE는 def/assignment가
 * 없으면 control(회귀 불변).
 */
import { useEffect, useMemo, useRef } from 'react';

import { track } from '../analytics/track';
import { assignLocal, ExperimentDef } from './client';

export interface UseVariantOptions {
  /** BE 권위 할당 맵(상위에서 fetchAssignments로 받은 것). 있으면 최우선. */
  assignments?: Record<string, string>;
  /** 로컬 폴백 실험 정의(오프라인/mock). */
  def?: ExperimentDef | null;
  /** 로컬 할당에 쓸 unit_id(user_id 또는 guest 토큰). */
  unit?: string | null;
  /** 노출 발행 여부(기본 true). control은 어차피 미노출. */
  expose?: boolean;
}

/** 우선순위에 따라 variant 문자열을 해석한다(부수효과 없음). */
export function resolveVariant(key: string, opts: UseVariantOptions = {}): string {
  const fromMap = opts.assignments?.[key];
  if (typeof fromMap === 'string' && fromMap.length > 0) return fromMap;
  if (opts.def) return assignLocal(opts.def, opts.unit);
  return 'control';
}

/**
 * useVariant(key, opts?) — variant 반환 + 노출 1회 발행.
 * 미지정·미해결 시 control 폴백. variant가 control이 아니고 expose!==false면 노출.
 */
export function useVariant(key: string, opts: UseVariantOptions = {}): string {
  const variant = useMemo(
    () => resolveVariant(key, opts),
    // assignments/def/unit이 바뀌면 재계산(opts 전체가 아니라 의미 있는 키만 의존).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key, opts.assignments, opts.def, opts.unit],
  );

  const exposedRef = useRef<string | null>(null);
  const expose = opts.expose !== false;

  useEffect(() => {
    if (!expose) return;
    if (variant === 'control') return; // control(미노출/홀드아웃)은 노출로 보지 않음
    // 같은 (key,variant) 조합은 1회만 발행(de-dup).
    const tag = `${key}:${variant}`;
    if (exposedRef.current === tag) return;
    exposedRef.current = tag;
    track('experiment_exposed', { experiment: key, variant });
  }, [key, variant, expose]);

  return variant;
}

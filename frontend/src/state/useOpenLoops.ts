/**
 * useOpenLoops — 미해결 스레드 표현 + 해소/닫기 mutation(요구 2).
 *
 * - 우선순위(priority) 내림차순 정렬해 노출(요구 1.3·2.1).
 * - resolve/dismiss → POST /open-loops/{ref}/{action}, **낙관적 제거** 후
 *   404/실패면 롤백 + 에러 표시(요구 2.4·2.5).
 *
 * 초기 목록은 resume의 open_loops[]를 받는다(소유는 useResume). 여기서는 로컬 표현 상태만 관리.
 */
import { useEffect, useState } from "react";
import { postOpenLoopAction, type ActionKind } from "../transport/companion";
import type { ApiConfig } from "../transport/api";
import type { OpenLoop } from "../types/contract";

export function sortByPriority(loops: OpenLoop[]): OpenLoop[] {
  return [...loops].sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
}

export function useOpenLoops(cfg: ApiConfig, source: OpenLoop[] | undefined) {
  const [loops, setLoops] = useState<OpenLoop[]>(() => sortByPriority(source ?? []));
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Set<string>>(new Set());

  // source(resume) 변경 시 동기화
  useEffect(() => {
    setLoops(sortByPriority(source ?? []));
  }, [source]);

  async function act(ref: string, action: ActionKind): Promise<boolean> {
    setError(null);
    const prev = loops;
    const removed = prev.find((l) => l.ref === ref);
    // 낙관적 제거(요구 2.4)
    setLoops((cur) => cur.filter((l) => l.ref !== ref));
    setPending((p) => new Set(p).add(ref));

    const res = await postOpenLoopAction(cfg, ref, action);

    setPending((p) => {
      const n = new Set(p);
      n.delete(ref);
      return n;
    });

    if (res.ok) return true;

    // 404/실패 → 롤백 + 에러 안내(요구 2.5)
    if (removed) setLoops(() => sortByPriority(prev));
    setError(
      res.notFound
        ? "이미 처리된 항목이에요. 목록을 새로고침했어요."
        : "처리에 실패했어요. 잠시 후 다시 시도해 주세요.",
    );
    return false;
  }

  return {
    loops,
    resolve: (ref: string) => act(ref, "resolve"),
    dismiss: (ref: string) => act(ref, "dismiss"),
    isPending: (ref: string) => pending.has(ref),
    error,
    clearError: () => setError(null),
  };
}

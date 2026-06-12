/**
 * useConsent — 선제/개인화 동의 게이트(R19 · ADR-0030/0042).
 *
 * 선제 재관여·개인화 요약을 노출하는 모든 훅이 의존하는 **게이트**다.
 * 미동의면 조회·노출 자체를 no-op으로 만들어(요구 6.1) 네트워크·노출을 원천 차단(깊이 방어).
 *
 * 코드베이스 관례(plain React, useHomeData 류)에 맞춰 외부 상태관리 의존 없이
 * 경량 모듈 스토어 + Context로 제공한다(zustand 미설치). 동의 변경 시 구독자에게 즉시 통지(요구 6.3).
 */
import React, { createContext, useContext, useEffect, useState } from "react";

export interface Consent {
  opted_in: boolean; // 선제/개인화 전반 동의
}

type Listener = (c: Consent) => void;

/** 모듈 스토어 — 동의 상태를 앱 전역에서 공유, 변경 시 구독자 즉시 통지. */
class ConsentStore {
  private state: Consent;
  private listeners = new Set<Listener>();

  constructor(initial: Consent) {
    this.state = initial;
  }
  get(): Consent {
    return this.state;
  }
  set(next: Partial<Consent>): void {
    this.state = { ...this.state, ...next };
    for (const l of this.listeners) l(this.state);
  }
  subscribe(l: Listener): () => void {
    this.listeners.add(l);
    return () => {
      this.listeners.delete(l);
    };
  }
}

const defaultStore = new ConsentStore({ opted_in: false });

const ConsentContext = createContext<ConsentStore>(defaultStore);

/** 테스트/앱에서 초기 동의 상태를 주입하는 Provider(미사용 시 기본 미동의). */
export function ConsentProvider({
  store,
  children,
}: {
  store?: ConsentStore;
  children: React.ReactNode;
}) {
  return <ConsentContext.Provider value={store ?? defaultStore}>{children}</ConsentContext.Provider>;
}

export function createConsentStore(initial: Consent): ConsentStore {
  return new ConsentStore(initial);
}

/** 현재 동의 상태 + 토글. 스토어 변경에 구독해 즉시 갱신(요구 6.3). */
export function useConsent() {
  const store = useContext(ConsentContext);
  const [consent, setConsent] = useState<Consent>(store.get());

  useEffect(() => {
    setConsent(store.get()); // 스토어가 바뀌면(테스트 Provider 교체) 즉시 동기화
    return store.subscribe(setConsent);
  }, [store]);

  return {
    consent,
    optedIn: consent.opted_in,
    setOptedIn: (v: boolean) => store.set({ opted_in: v }),
  };
}

export type { ConsentStore };

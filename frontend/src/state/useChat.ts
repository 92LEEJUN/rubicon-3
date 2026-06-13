/** useChat — 트랜스포트 청크를 reducer로 누적(frontend-architecture §11 훅 카탈로그). */
import { useEffect, useReducer, useRef } from 'react';
import type { ChatTransport } from '../transport';
import type { Cta } from '../types/contract';
import { chatReducer, initialChat } from './chat';

export function useChat(transport: ChatTransport) {
  const [state, dispatch] = useReducer(chatReducer, initialChat);
  const ready = useRef(false);

  useEffect(() => {
    transport.onChunk((c) => dispatch(c));
    transport.connect();
    ready.current = true;
    return () => transport.close();
  }, [transport]);

  function send(text: string, screenContext?: Record<string, unknown>) {
    dispatch({ type: 'send' });
    transport.send({ type: 'user_message', text, screen_context: screenContext ?? null });
  }
  function replyInteraction(cta: Cta) {
    dispatch({ type: 'send' });
    transport.send({
      type: 'interaction_reply',
      kind: cta.kind ?? 'choices',
      payload: cta.payload ?? {},
    });
  }
  /**
   * resumeFromRef — open-loop/선제 배너 탭 시 해당 ref 맥락으로 /chat 재진입(요구 2.2·3.3).
   * 맥락(ref·진입 출처)을 screen_context로 주입해 proactive→reactive로 대화를 잇는다.
   * 전송은 기존 user_message 봉투를 재사용(새 BE 계약 만들지 않음).
   */
  function resumeFromRef(ref: string, screenContext?: Record<string, unknown>) {
    dispatch({ type: 'send' });
    transport.send({
      type: 'user_message',
      text: '', // 맥락 기반 재진입 — 본문은 비우고 ref로 이어간다
      screen_context: { ...(screenContext ?? {}), resume_ref: ref },
    });
  }
  return { state, send, replyInteraction, resumeFromRef };
}

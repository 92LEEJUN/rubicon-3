/** useChat — 트랜스포트 청크를 reducer로 누적(frontend-architecture §11 훅 카탈로그). */
import { useEffect, useReducer, useRef } from "react";
import type { ChatTransport } from "../transport";
import type { Cta } from "../types/contract";
import { chatReducer, initialChat } from "./chat";

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
    dispatch({ type: "send" });
    transport.send({ type: "user_message", text, screen_context: screenContext ?? null });
  }
  function replyInteraction(cta: Cta) {
    dispatch({ type: "send" });
    transport.send({ type: "interaction_reply", kind: cta.kind ?? "choices", payload: cta.payload ?? {} });
  }
  return { state, send, replyInteraction };
}

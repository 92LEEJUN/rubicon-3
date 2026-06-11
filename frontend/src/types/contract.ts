/**
 * FE↔BFF 공유 계약 타입(api-contract §2 · response-templates · data-model).
 * BFF가 보내는 청크/섹션/템플릿을 그대로 렌더한다(FE는 BFF 계약만 본다).
 */
export type CtaAction = "chat" | "commit" | "navigate";

export interface Cta {
  label: string;
  action: CtaAction;
  kind?: string;
  payload?: Record<string, unknown>;
}

export interface Template<T = Record<string, any>> {
  kind: string; // device_status · guide_steps · product_card · order_summary · confirmation · recommendation_list · home_summary · text ...
  data: T;
}

export interface MessageSection {
  label: string;
  intent: string;
  template: Template;
  ctas: Cta[];
  handled: boolean;
}

/** WS /chat 서버→클라이언트 청크(api-contract §2.1) */
export type Chunk =
  | { type: "delta"; text: string }
  | { type: "section"; section: MessageSection }
  | { type: "flow"; active_flow: string | null }
  | { type: "done"; message_id?: string }
  | { type: "error"; code: string; fallback?: Template; message?: string };

/** 클라이언트→서버 메시지 */
export type ClientMessage =
  | { type: "user_message"; session_id?: string; text: string; screen_context?: Record<string, unknown> | null }
  | { type: "interaction_reply"; session_id?: string; ref?: string; kind: string; payload: Record<string, unknown> };

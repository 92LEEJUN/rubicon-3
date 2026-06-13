/**
 * FE↔BFF 공유 계약 타입(api-contract §2 · response-templates · data-model).
 * BFF가 보내는 청크/섹션/템플릿을 그대로 렌더한다(FE는 BFF 계약만 본다).
 */
export type CtaAction = "chat" | "commit" | "navigate";

/**
 * 알려진 CTA kind(계약). `kind`는 permissive(string)로 두되 — BFF가 새 kind를 보내도
 * 깨지지 않게 — 코드가 분기하는 알려진 값은 여기에 열거한다.
 *  - commit 계열: `order`·`booking`(action:"commit" → REST commit 라운드트립, §commit).
 *  - 게이트/흐름: `login`(로그인 월 트리거), `select_device`(payload.device_id로 **즉시 질의 전송**, 입력 편집 아님).
 *  - 후속 대화(chat): `booking`(advisory)·`restock_alert`·`compare`·`explain`·`recommend` 등 →
 *    interaction_reply/user_message 후속으로 전송.
 */
export type CtaKind =
  | "order"
  | "booking"
  | "login"
  | "select_device"
  | "restock_alert"
  | "compare"
  | "explain"
  | "recommend"
  | "choices"
  | "handoff";

export interface Cta {
  label: string;
  action: CtaAction;
  kind?: CtaKind | string; // 알려진 값은 CtaKind, 미지의 kind도 허용(permissive)
  payload?: Record<string, unknown>;
}

/**
 * 알려진 template kind(계약). `kind`는 permissive(string) — 미등록 kind는 text 폴백(§7).
 * 코드가 렌더러를 가진 알려진 값은 여기에 열거한다.
 *  - 신규: `booking`(data: {visit_type?, slots:[{id,start,end}...]}) — 방문 슬롯 리스트.
 *  - clarify/warranty/explain 섹션도 이 kind들(text·recommendation_list·booking)을 재사용한다.
 */
export type TemplateKind =
  | "text"
  | "device_status"
  | "guide_steps"
  | "product_card"
  | "order_summary"
  | "confirmation"
  | "recommendation_list"
  | "home_summary"
  | "status_tracker"
  | "bridge"
  | "handoff_card"
  | "booking"
  | "choices";

export interface Template<T = Record<string, any>> {
  kind: TemplateKind | string; // 알려진 값은 TemplateKind, 미지의 kind는 text 폴백(§7)
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

/**
 * 컴패니언 DTO(api-contract §2.2 · always-present-companion design).
 * BFF가 보내는 형태를 그대로 받아 렌더한다(FE는 BFF 계약만 본다 — 재정의가 아니라 대응 타입).
 */

/** 미해결 스레드(always-present-companion: OpenLoop). */
export type OpenLoopKind = "issue" | "order" | "flow";
export type OpenLoopStatus = "open" | "resolved" | "dismissed";

export interface OpenLoop {
  id: string;
  kind: OpenLoopKind;
  ref: string;
  status: OpenLoopStatus;
  priority: number; // 클수록 우선(우선순위 정렬용)
  opened_at?: string;
  last_touch?: string;
  summary?: string; // 표시용 요약(라벨)
}

/** 이어가기(resume) 페이로드(api-contract §2.2). */
export interface ResumePayload {
  has_context: boolean;
  summary?: string;
  facts?: Record<string, unknown>;
  open_loops?: OpenLoop[];
  elapsed_label?: string; // 상대 시간 표현(예: "어제")
  suspended_flow?: string | null;
  personalized?: boolean; // 요약이 개인화(메모리)에 의존하면 true → 동의 게이트 대상
}

/** 선제 재관여(api-contract §2.2). `{}`이면 없음. */
export interface ReEngagement {
  primary_ref?: string;
  primary_label?: string;
  kind?: string;
  also_count?: number;
  message?: string;
}

/**
 * 자동 생성 (scripts/gen_types.py) — 편집 금지.
 * 출처: OpenAPI(x-api-version=2025-06-01). 정본 계약은 contract.ts(손-작성).
 * 이 파일은 BE 스키마→TS 드리프트 점검 보조다(ADR-0060 · api-contract §7.4).
 */

export interface BookingRequest {
  slot_id: string;
  context_ref?: string | null;
  visit_type?: string;
  store_id?: string | null;
  confirmed?: boolean;
  user_id?: string | null;
  guest_token?: string | null;
}

export interface ConvertRequest {
  user_id?: string;
  confirmed?: boolean;
  fulfillment?: string;
  store_id?: string | null;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface MergeRequest {
  guest_token: string;
  user_id: string;
}

export interface OrderRequest {
  user_id?: string;
  part_ids: string[];
  confirmed?: boolean;
  fulfillment?: string;
  store_id?: string | null;
  guest_token?: string | null;
}

export interface PickupActionRequest {
  action: string;
}

export interface SurfaceRequest {
  card_type: string;
  ref?: string | null;
  screen_context?: Record<string, unknown> | null;
}

export interface TurnRequest {
  session_id?: string;
  text: string;
  media?: unknown[];
  screen_context?: Record<string, unknown> | null;
  user_id?: string | null;
  guest_token?: string | null;
}

export interface ValidationError {
  loc: string | number[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}


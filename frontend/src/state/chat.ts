/**
 * 채팅 스트림 환원(reducer) — WS 청크를 메시지+섹션 리스트+스트리밍 상태로 누적.
 * frontend-architecture §11(1) 채팅 스트림 환원. 복합(R7)은 section 청크를 순서대로 쌓는다.
 */
import type { Chunk, MessageSection, Template } from '../types/contract';

export interface ChatState {
  status: 'idle' | 'streaming' | 'done' | 'error';
  sections: MessageSection[];
  assistantText: string; // LLM 자연어 답변(delta 누적) — 섹션과 별개로 노출
  activeFlow: string | null;
  messageId?: string;
  error?: { code: string; message?: string; fallback?: Template };
}

export const initialChat: ChatState = {
  status: 'idle',
  sections: [],
  assistantText: '',
  activeFlow: null,
};

export type ChatAction = Chunk | { type: 'send' } | { type: 'reset' };

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'send':
      // 새 턴 시작 — 이전 섹션·텍스트 비우고 스트리밍 진입
      return { status: 'streaming', sections: [], assistantText: '', activeFlow: null };
    case 'reset':
      return initialChat;
    case 'section':
      return { ...state, status: 'streaming', sections: [...state.sections, action.section] };
    case 'flow':
      return { ...state, activeFlow: action.active_flow };
    case 'done':
      return { ...state, status: 'done', messageId: action.message_id };
    case 'error':
      return {
        ...state,
        status: 'error',
        error: { code: action.code, message: action.message, fallback: action.fallback },
        // 폴백 템플릿이 있으면 텍스트 섹션으로 노출(대화 중단 금지, R13)
        sections: action.fallback
          ? [...state.sections, fallbackSection(action.fallback)]
          : state.sections,
      };
    case 'delta':
      // LLM 자연어 토큰/덩어리 누적
      return { ...state, status: 'streaming', assistantText: state.assistantText + action.text };
    default:
      return state;
  }
}

function fallbackSection(fallback: Template): MessageSection {
  return { label: '안내', intent: 'general', handled: false, ctas: [], template: fallback };
}

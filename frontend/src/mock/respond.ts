/** Mock 채팅 응답(ADR-0051) — 시나리오 스크립트 + 키워드 라우터 → §2.1 봉투(section*→flow→done).
 *  BE capability 라우팅을 미러(backend-architecture §3). 실연동 미연결 시 LiveChat/ChatPanel이 사용. */
import type { Chunk, MessageSection } from "../types/contract";
import {
  buildBooking, buildClarify, buildDiagnose, buildExplain, buildGeneral,
  buildOrder, buildRecommend, buildWarranty,
} from "./sections";

const BUILDERS: Record<string, (t: string) => MessageSection[]> = {
  diagnose: buildDiagnose,
  warranty: buildWarranty,
  booking: () => buildBooking(),
  explain: () => buildExplain(),
  recommend: () => buildRecommend(),
  order: buildOrder,
  clarify: () => buildClarify(),
  general: () => buildGeneral(),
};
// 우선순위(안전·진단 먼저, 주문 뒤) — backend _PRIORITY 미러.
const ORDER = ["diagnose", "warranty", "explain", "booking", "recommend", "general", "clarify", "order"];

/** 정의된 데모 저니 → 고정 intent 시퀀스(시나리오 재생). */
const SCRIPTS: { match: RegExp; intents: string[] }[] = [
  { match: /물.*안.*빠|5c|배수/i, intents: ["diagnose", "order"] },            // J1 세탁기
  { match: /보증.*예약|무상.*기사|보증.*기사|예약.*보증/, intents: ["warranty", "booking"] }, // F2
  { match: /이사|새 아파트|장만|추천/, intents: ["recommend"] },               // J3 추천
];

/** 자유 입력 → intent 집합(키워드 라우터, 폴백). */
function keywordIntents(text: string): string[] {
  const t = text || "";
  const set = new Set<string>();
  if (/보증|무상|a\/s|as센터|에이에스/i.test(t)) set.add("warranty");
  if (/예약|방문|기사/.test(t)) set.add("booking");
  if (/더 알려|비교|스펙|얼마|가격|차이/.test(t)) set.add("explain");
  if (/추천|장만|뭐가 좋|새로 사|구입할/.test(t)) set.add("recommend");
  if (/주문|사줘|구매|담아|장바구니/.test(t)) set.add("order");
  if (/안 ?돼|안돼|고장|에러|오류|해결|증상|냄새|소리|물|5c/i.test(t)) set.add("diagnose");
  return [...set];
}

function intentsFor(text: string): string[] {
  const script = SCRIPTS.find((s) => s.match.test(text));
  if (script) return script.intents;
  const kw = keywordIntents(text);
  if (kw.length) return kw;
  // 아무것도 안 잡히면: 짧고 모호하면 clarify, 인사/그 외 general
  return (text || "").trim().length <= 6 ? ["clarify"] : ["clarify"];
}

/** mock 응답 청크 생성. */
export function respond(text: string): Chunk[] {
  const intents = intentsFor(text).sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b));
  const sections: MessageSection[] = [];
  for (const name of intents) {
    const build = BUILDERS[name];
    if (build) sections.push(...build(text));
  }
  if (!sections.length) sections.push(...buildClarify());

  const flow = sections.some((s) => s.intent === "troubleshoot") ? "troubleshoot" : null;
  const chunks: Chunk[] = [{ type: "delta", text: "데모 모드 — 예시 응답이에요." }];
  for (const section of sections) chunks.push({ type: "section", section });
  chunks.push({ type: "flow", active_flow: flow });
  chunks.push({ type: "done", message_id: `msg_mock_${Date.now().toString(36)}` });
  return chunks;
}

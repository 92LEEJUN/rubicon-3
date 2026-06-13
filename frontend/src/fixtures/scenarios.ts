/**
 * 요구사항 데모 시나리오 — R1~R29를 채팅 트랜스크립트로 화면화(스크린샷용).
 * 각 메시지에 reqs(R#)를 달아 화면에 배지로 표기한다. 섹션 템플릿은 journeys fixtures 재사용.
 * 커버리지: s1~s10 합집합 = R1~R29 (journeys.md / requirements.md 매핑).
 */
import type { MessageSection, Template } from '../types/contract';
import {
  j1Sections,
  recommendation,
  confirmation,
  statusTracker,
  bridge,
  handoffCard,
  booking,
  j5UnhandledHepa,
} from './journeys';

const S = (
  label: string,
  intent: string,
  template: Template,
  ctas: any[] = [],
  handled = true,
): MessageSection => ({ label, intent, template, ctas, handled });

export interface ScenarioMsg {
  role: 'user' | 'assistant' | 'system';
  text?: string;
  image?: string; // 사용자 멀티모달 첨부(R10)
  note?: string; // system 안내(온보딩·동의·인증 등)
  sections?: MessageSection[];
  reqs?: string[]; // 이 메시지가 충족하는 요구사항(R#)
}

export interface Scenario {
  id: string;
  title: string;
  reqs: string[];
  messages: ScenarioMsg[];
}

// 데모 썸네일(데이터 URI) — 멀티모달 첨부 표현
const PHOTO =
  'data:image/svg+xml,' +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='80' height='60'><rect width='80' height='60' rx='8' fill='#5A6068'/><circle cx='26' cy='22' r='9' fill='#FDF3E0'/><path d='M8 52 L30 32 L46 46 L60 30 L72 42 L72 60 L8 60 Z' fill='#8B9097'/></svg>",
  );

export const SCENARIOS: Scenario[] = [
  // ── J1-a: 진입 → 진단 → 해결(출처·안전) ──────────────────────────────────
  {
    id: 's1',
    title: 'J1 · 세탁기 5C 진단·해결',
    reqs: ['R1', 'R2', 'R3', 'R9', 'R16', 'R23'],
    messages: [
      { role: 'system', note: '🏠 홈에서 채팅 진입 · 화면 맥락(세탁기) 주입', reqs: ['R9'] },
      { role: 'user', text: '세탁기에서 물이 안 빠져요.' },
      {
        role: 'assistant',
        text: '세탁기 상태를 확인했어요. 배수 이상(5C)이 감지됐습니다.',
        reqs: ['R1', 'R2'],
        sections: [j1Sections[0]],
      },
      {
        role: 'assistant',
        text: 'CS 데이터 기준 단계별 해결 방법이에요. 2단계는 감전 위험이 있어 전원을 꼭 끄세요.',
        reqs: ['R3', 'R16', 'R23'],
        sections: [j1Sections[1]],
      },
    ],
  },
  // ── J1-b: 부품 → 확인 게이트 → 주문 → 추적(스트리밍·CTA·이력) ──────────────
  {
    id: 's2',
    title: 'J1 · 부품 주문·확인·추적',
    reqs: ['R4', 'R11', 'R14', 'R17', 'R12'],
    messages: [
      {
        role: 'assistant',
        text: '해결에 필요한 배수 필터를 찾았어요. (스트리밍·타이핑으로 점진 표시)',
        reqs: ['R4', 'R11', 'R14'],
        sections: [j1Sections[2]],
      },
      { role: 'user', text: '주문할게요' },
      {
        role: 'assistant',
        text: '결제 전 한 번 더 확인해 주세요. 되돌릴 수 없는 작업이에요.',
        reqs: ['R17'],
        sections: [S('주문 확인', 'order', confirmation)],
      },
      { role: 'user', text: '결제 진행' },
      {
        role: 'assistant',
        text: '주문이 확정됐어요. 진행 상태는 여기서 추적할 수 있어요.',
        reqs: ['R12'],
        sections: [S('진행 추적', 'order', statusTracker)],
      },
    ],
  },
  // ── J2: 선제 재주문(동의·빈도·무상·중복억제) ──────────────────────────────
  {
    id: 's3',
    title: 'J2 · 정수필터 선제 재주문',
    reqs: ['R5', 'R20', 'R22', 'R26', 'R29'],
    messages: [
      {
        role: 'system',
        note: '🔔 선제 알림 — 수신 동의 ON · 빈도/중요도 게이트 통과분만 전달',
        reqs: ['R20', 'R26'],
      },
      {
        role: 'assistant',
        text: '냉장고 정수필터 수명이 임계치에 도달해 교체 시기를 미리 알려드려요. 무상 보증 대상입니다.',
        reqs: ['R5', 'R22'],
        sections: [
          S('빠른 보기', 'device_status', bridge, [
            {
              label: '재주문',
              action: 'commit',
              kind: 'order',
              payload: { part_ids: ['part_water_filter'] },
            },
          ]),
        ],
      },
      { role: 'user', text: '재주문할게요' },
      {
        role: 'assistant',
        text: '확인 후 주문해 드릴게요. (이미 확인한 알림은 다시 띄우지 않아요)',
        reqs: ['R29', 'R17'],
        sections: [S('주문 확인', 'order', confirmation)],
      },
    ],
  },
  // ── J3: 품절 → 폴백 → 개인화 추천(근거) ───────────────────────────────────
  {
    id: 's4',
    title: 'J3 · HEPA 품절·대체·추천',
    reqs: ['R4', 'R8', 'R13', 'R29'],
    messages: [
      { role: 'user', text: '공기청정기 HEPA 필터 주문해줘' },
      {
        role: 'assistant',
        text: '해당 필터는 현재 품절이에요. 대화를 끊지 않고 대안을 안내할게요.',
        reqs: ['R4', 'R13'],
        sections: [j5UnhandledHepa],
      },
      {
        role: 'assistant',
        text: '이전에 공기청정기에 관심을 보이셔서, 보유 기기를 보완하는 신제품을 추천해요.',
        reqs: ['R8', 'R29'],
        sections: [recommendation],
      },
    ],
  },
  // ── J4: 셀프 실패 → 핸드오프 → 예약 → 수리 후 피드백 ──────────────────────
  {
    id: 's5',
    title: 'J4 · 방문 예약 핸드오프',
    reqs: ['R3', 'R16', 'R18', 'R25'],
    messages: [
      { role: 'user', text: '가이드대로 해도 안 돼요' },
      {
        role: 'assistant',
        text: '직접 해결이 어려운 상황으로 판단돼요. 무리하지 않도록 전문 기사 방문을 권해요.',
        reqs: ['R16', 'R18'],
        sections: [
          S('방문 안내', 'general', handoffCard, [
            { label: '방문 예약', action: 'chat', kind: 'handoff' },
          ]),
        ],
      },
      { role: 'user', text: '방문 예약할게요' },
      {
        role: 'assistant',
        text: '가능한 방문 시간을 골라주세요. 시도한 해결 맥락은 기사에게 함께 전달돼요.',
        reqs: ['R18'],
        sections: [S('예약 슬롯', 'general', booking)],
      },
      { role: 'system', note: '🛠 방문 수리 완료 후 — 해결 여부 확인·피드백 요청', reqs: ['R25'] },
      {
        role: 'assistant',
        text: '수리는 잘 마무리되셨나요? 피드백을 남겨주시면 개선에 반영할게요.',
        reqs: ['R25'],
      },
    ],
  },
  // ── J5: 복합 질문 → 분해·우선순위·부분 처리 ───────────────────────────────
  {
    id: 's6',
    title: 'J5 · 복합 질문 분해·부분 처리',
    reqs: ['R7', 'R13'],
    messages: [
      {
        role: 'user',
        text: '세탁기 물 안 빠지는 거 해결법 알려주고, 냉장고 정수필터랑 공기청정기 HEPA 필터도 주문해줘',
      },
      {
        role: 'assistant',
        text: '의도 3개로 분해했어요: ① 세탁기 해결 ② 정수필터 주문 ③ HEPA 주문. 안전·CS를 먼저 처리합니다.',
        reqs: ['R7'],
        sections: [
          j1Sections[1],
          S('부품 주문', 'order', {
            kind: 'product_card',
            data: {
              id: 'part_water_filter',
              name: '냉장고 정수필터',
              sku: 'HAF-QIN',
              price: 38000,
              in_stock: true,
            },
          }),
          j5UnhandledHepa,
        ],
      },
      {
        role: 'assistant',
        text: '처리: [세탁기 해결, 정수필터 주문] · 미처리: [HEPA(품절)] — 부분 실패는 전체를 막지 않아요.',
        reqs: ['R7', 'R13'],
      },
    ],
  },
  // ── 보조 1: 멀티모달 · 흐름 중 채팅 전환·복귀 ─────────────────────────────
  {
    id: 's7',
    title: '보조 · 멀티모달·맥락 전환',
    reqs: ['R6', 'R10'],
    messages: [
      { role: 'user', text: '이 부품 어디에 끼우나요? 사진 첨부해요', image: PHOTO, reqs: ['R10'] },
      {
        role: 'assistant',
        text: '사진을 확인했어요. 영상 가이드로 장착 위치를 보여드릴게요.',
        reqs: ['R10'],
        sections: [
          S('해결 가이드', 'troubleshoot', {
            kind: 'guide_steps',
            data: {
              coverage: 'unknown',
              steps: [
                {
                  order: 1,
                  instruction: '하단 커버를 열고 필터를 끼웁니다.',
                  safety: 'none',
                  media: [
                    { type: 'video', title: '장착 영상' },
                    { type: 'image', title: '장착 위치' },
                  ],
                },
              ],
            },
          }),
        ],
      },
      { role: 'user', text: '그런데 보증 기간은 언제까지야?' },
      {
        role: 'assistant',
        text: '가이드 도중이라도 자유 질문에 바로 답해요(맥락 유지). 끝나면 원래 해결 흐름으로 다시 이어갈게요.',
        reqs: ['R6'],
      },
    ],
  },
  // ── 보조 2: 미연동 온보딩 · 범위 밖 · 인증 ────────────────────────────────
  {
    id: 's8',
    title: '보조 · 온보딩·범위밖·인증',
    reqs: ['R1', 'R15', 'R24'],
    messages: [
      {
        role: 'system',
        note: '🔐 인증된 사용자: 홍길동 · 연동 동의 범위 안에서만 기기 데이터 사용',
        reqs: ['R15'],
      },
      { role: 'user', text: '오늘 날씨 어때?' },
      {
        role: 'assistant',
        text: '저는 삼성 가전·CS·주문을 도와드려요. 날씨는 제 범위 밖이라 도와드리기 어려워요.',
        reqs: ['R1'],
      },
      { role: 'user', text: '내 세탁기 상태 봐줘' },
      {
        role: 'assistant',
        text: '아직 연동된 기기가 없어요. SmartThings를 연동하면 상태·이상 진단을 받을 수 있어요. (미연동도 일반 안내는 계속 가능)',
        reqs: ['R24', 'R13'],
        sections: [
          S(
            '연동 안내',
            'general',
            {
              kind: 'text',
              data: {
                message: 'SmartThings 계정을 연동하고 기기 진단을 시작하세요.',
              },
            },
            [{ label: '기기 연동하기', action: 'navigate', kind: 'onboarding' }],
          ),
        ],
      },
    ],
  },
  // ── 보조 3: 동의/삭제 · 취소/환불 · 분석 ──────────────────────────────────
  {
    id: 's9',
    title: '보조 · 동의·취소·분석',
    reqs: ['R19', 'R21', 'R28'],
    messages: [
      { role: 'user', text: '아까 그 주문 취소하고 환불해줘' },
      {
        role: 'assistant',
        text: '주문을 취소하고 환불을 접수했어요.',
        reqs: ['R21'],
        sections: [
          S('주문 취소', 'order', {
            kind: 'order_summary',
            data: {
              order: {
                id: 'ord_0001',
                status: 'CANCELLED',
                items: [{ name: '세탁기 배수 필터', unit_price: 12000, qty: 1 }],
              },
              summary: { subtotal: 12000, shipping_fee: 0, discount: 0, total: 0 },
            },
          }),
        ],
      },
      { role: 'user', text: '내 개인정보·대화 데이터 삭제할 수 있어?' },
      {
        role: 'assistant',
        text: '네. 동의 범위 내에서만 데이터를 쓰고, 요청 시 개인화·대화 데이터를 삭제해 드려요.',
        reqs: ['R19'],
      },
      {
        role: 'system',
        note: '📊 대화·전환은 익명 집계로 서비스 개선에 활용(동의 기반)',
        reqs: ['R28'],
      },
    ],
  },
  // ── 보조 4: 다중 기기 이상 우선순위 · 이력 ────────────────────────────────
  {
    id: 's10',
    title: '보조 · 다중 기기 우선순위',
    reqs: ['R2', 'R12', 'R27'],
    messages: [
      { role: 'user', text: '내 기기들 상태 다 알려줘. 지난 주문도 같이.' },
      {
        role: 'assistant',
        text: '여러 이상을 심각도 순으로 정렬했어요: 세탁기(점검) → 냉장고(소모품) → 공기청정기(소모품).',
        reqs: ['R2', 'R27'],
        sections: [
          S('기기 상태', 'device_status', j1Sections[0].template),
          S('빠른 보기', 'device_status', bridge),
        ],
      },
      {
        role: 'assistant',
        text: '지난 주문·서비스 이력도 함께 조회했어요.',
        reqs: ['R12'],
        sections: [S('진행 추적', 'order', statusTracker)],
      },
    ],
  },
];

export function getScenario(id?: string): Scenario {
  return SCENARIOS.find((s) => s.id === id) ?? SCENARIOS[0];
}

/** 증분 스트리밍 reducer — delta→section(순서)→flow→done/error 시퀀스(요구 4, 작업 2.6). */
import { chatReducer, initialChat } from '../src/state/chat';
import type { MessageSection } from '../src/types/contract';

function section(intent: string): MessageSection {
  return {
    label: intent,
    intent,
    handled: true,
    ctas: [],
    template: { kind: 'text', data: { message: intent } },
  };
}

test('delta 청크는 진행 텍스트를 누적한다(요구 4.1)', () => {
  let s = chatReducer(initialChat, { type: 'send' });
  s = chatReducer(s, { type: 'delta', text: '안녕' });
  s = chatReducer(s, { type: 'delta', text: '하세요' });
  expect(s.assistantText).toBe('안녕하세요');
  expect(s.status).toBe('streaming');
});

test('section 청크는 도착 순서대로 세로 스택에 쌓인다(요구 4.2)', () => {
  let s = chatReducer(initialChat, { type: 'send' });
  for (const i of ['a', 'b', 'c']) s = chatReducer(s, { type: 'section', section: section(i) });
  expect(s.sections.map((x) => x.intent)).toEqual(['a', 'b', 'c']);
});

test('전체 시퀀스 delta→section→flow→done 환원(요구 4.1~4.5)', () => {
  let s = chatReducer(initialChat, { type: 'send' });
  s = chatReducer(s, { type: 'delta', text: '리드' });
  s = chatReducer(s, { type: 'section', section: section('device_status') });
  s = chatReducer(s, { type: 'section', section: section('order') });
  s = chatReducer(s, { type: 'flow', active_flow: 'troubleshoot' });
  expect(s.status).toBe('streaming');
  s = chatReducer(s, { type: 'done', message_id: 'm1' });
  expect(s.status).toBe('done');
  expect(s.activeFlow).toBe('troubleshoot');
  expect(s.messageId).toBe('m1');
  expect(s.sections.map((x) => x.intent)).toEqual(['device_status', 'order']);
  expect(s.assistantText).toBe('리드');
});

test('error 청크는 fallback 섹션을 삽입하고 누적 섹션을 보존한다(요구 4.5·5.2)', () => {
  let s = chatReducer(initialChat, { type: 'send' });
  s = chatReducer(s, { type: 'section', section: section('device_status') });
  s = chatReducer(s, {
    type: 'error',
    code: 'upstream',
    fallback: { kind: 'text', data: { message: '잠시 후' } },
  });
  expect(s.status).toBe('error');
  // 기존 섹션 유지 + 폴백 섹션 추가(대화 미중단)
  expect(s.sections).toHaveLength(2);
  expect(s.sections[1].handled).toBe(false);
  expect(s.sections[1].template.kind).toBe('text');
});

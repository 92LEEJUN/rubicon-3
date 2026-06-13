/** 섹션/메시지 렌더 — 복합 스택·미처리 표시·CTA(R7). */
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MessageView } from '../src/components/message';
import { j1Sections, j5UnhandledHepa } from '../src/fixtures/journeys';

test('renders one card per section (복합 R7)', () => {
  render(<MessageView sections={j1Sections} />);
  expect(screen.getByTestId('section-device_status')).toBeInTheDocument();
  expect(screen.getByTestId('section-troubleshoot')).toBeInTheDocument();
  expect(screen.getByTestId('section-order')).toBeInTheDocument();
});

test('unhandled section shows toned-down affordance (R7-3, 요구 ⑦)', () => {
  render(<MessageView sections={[j5UnhandledHepa]} />);
  // 정상 답변처럼 보이지 않게 — 톤다운 안내 + 보류 배지(일반 카드 렌더 아님).
  expect(screen.getByText('이건 아직 도와드리기 어려워요.')).toBeInTheDocument();
  expect(screen.getByText('처리 보류')).toBeInTheDocument();
});

test('CTA press fires handler', () => {
  const onCta = jest.fn();
  render(<MessageView sections={j1Sections} onCta={onCta} />);
  fireEvent.click(screen.getAllByTestId('cta-order')[0]);
  expect(onCta).toHaveBeenCalledTimes(1);
  expect(onCta.mock.calls[0][0].kind).toBe('order');
});

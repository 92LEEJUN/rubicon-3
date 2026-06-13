/** booking 템플릿 렌더 · 미처리 톤다운 · 분석 track 배선(요구 ④⑦⑨). */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MessageView } from '../src/components/message';
import { bookingSection, j5UnhandledHepa } from '../src/fixtures/journeys';
import { track, setAnalyticsSink } from '../src/analytics/track';

test('booking 섹션 — 슬롯 리스트 + 방문유형 + 예약 확정 commit CTA(요구 ④⑩)', () => {
  render(<MessageView sections={[bookingSection]} />);
  expect(screen.getByText('방문 시간 선택')).toBeInTheDocument();
  expect(screen.getByTestId('slot-0')).toBeInTheDocument();
  expect(screen.getByTestId('slot-1')).toBeInTheDocument();
  expect(screen.getByText('출장 수리')).toBeInTheDocument(); // visit_type 라벨
  // commit CTA(kind:booking)는 SectionView → CtaRow로 노출
  expect(screen.getByTestId('cta-booking')).toBeInTheDocument();
});

test('booking commit CTA 탭 → onCta(kind booking, action commit) 라우팅(요구 ⑥)', () => {
  const onCta = jest.fn();
  render(<MessageView sections={[bookingSection]} onCta={onCta} />);
  fireEvent.click(screen.getByTestId('cta-booking'));
  expect(onCta).toHaveBeenCalledTimes(1);
  expect(onCta.mock.calls[0][0]).toMatchObject({ action: 'commit', kind: 'booking' });
});

test('미처리 섹션 — 톤다운 안내 + 대안 CTA 유지(요구 ⑦)', () => {
  const onCta = jest.fn();
  render(<MessageView sections={[j5UnhandledHepa]} onCta={onCta} />);
  expect(screen.getByText('이건 아직 도와드리기 어려워요.')).toBeInTheDocument();
  // 대안 행동(입고 알림) CTA는 남는다
  fireEvent.click(screen.getByTestId('cta-restock_alert'));
  expect(onCta).toHaveBeenCalledTimes(1);
  expect(onCta.mock.calls[0][0].kind).toBe('restock_alert');
});

test('track — 커스텀 싱크로 이벤트 발행, no-op 가능(요구 ⑨)', () => {
  const seen: Array<[string, any]> = [];
  setAnalyticsSink((n, p) => seen.push([n, p]));
  track('cta_clicked', { cta: 'order' });
  track('message_sent', { modality: 'text' });
  expect(seen).toEqual([
    ['cta_clicked', { cta: 'order' }],
    ['message_sent', { modality: 'text' }],
  ]);
  setAnalyticsSink(null); // no-op으로 복구 — 던지지 않음
  expect(() => track('order_confirmed')).not.toThrow();
});

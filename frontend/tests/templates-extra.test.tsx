/** 추가 템플릿 — status_tracker·bridge·handoff_card·booking + 갤러리. */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { TemplateView } from '../src/templates';
import { Gallery } from '../src/screens/Gallery';
import { statusTracker, bridge, handoffCard, booking } from '../src/fixtures/journeys';

test('status_tracker renders steps', () => {
  render(<TemplateView template={statusTracker} />);
  expect(screen.getByText('주문 확정')).toBeInTheDocument();
  expect(screen.getByText('배송 중')).toBeInTheDocument();
});

test('bridge renders nested device status summary', () => {
  render(<TemplateView template={bridge} />);
  expect(screen.getByText('빠른 보기')).toBeInTheDocument();
  expect(screen.getByText(/RF28R7351SR/)).toBeInTheDocument();
});

test('handoff_card renders visit type', () => {
  render(<TemplateView template={handoffCard} />);
  expect(screen.getByText('출장 수리')).toBeInTheDocument();
});

test('booking renders slots', () => {
  render(<TemplateView template={booking} />);
  expect(screen.getAllByText('선택 가능').length).toBeGreaterThanOrEqual(1);
});

test('gallery renders all template kinds', () => {
  render(<Gallery />);
  expect(screen.getByTestId('screen-gallery')).toBeInTheDocument();
  expect(screen.getByText('응답 템플릿 갤러리')).toBeInTheDocument();
});

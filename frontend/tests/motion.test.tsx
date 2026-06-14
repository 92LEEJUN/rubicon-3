/**
 * 모션 프리미티브 테스트(ADR-0068) — jsdom에서 **콘텐츠·접근성·기능**만 검증한다.
 * 모션 타이밍은 검증하지 않는다(요구 4-2). framer-motion × react-native-web 통합 회귀 가드.
 */
import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import { Text } from 'react-native';
import { FadeInView, PressableScale, Stagger, StaggerItem } from '../src/components/motion';
import { Skeleton, SkeletonCard } from '../src/components/Skeleton';
import { Card, Button } from '../src/components/primitives';

test('FadeInView renders its children content', () => {
  const { queryByText } = render(
    <FadeInView testID="fade">
      <Text>fade-content</Text>
    </FadeInView>
  );
  expect(queryByText('fade-content')).toBeTruthy();
});

test('Stagger/StaggerItem render all children', () => {
  const { queryByText } = render(
    <Stagger testID="stag">
      <StaggerItem>
        <Text>item-a</Text>
      </StaggerItem>
      <StaggerItem>
        <Text>item-b</Text>
      </StaggerItem>
    </Stagger>
  );
  expect(queryByText('item-a')).toBeTruthy();
  expect(queryByText('item-b')).toBeTruthy();
});

test('PressableScale fires onPress and keeps content', () => {
  const onPress = jest.fn();
  const { getByTestId, queryByText } = render(
    <PressableScale testID="press" onPress={onPress}>
      <Text>tap-me</Text>
    </PressableScale>
  );
  expect(queryByText('tap-me')).toBeTruthy();
  fireEvent.click(getByTestId('press'));
  expect(onPress).toHaveBeenCalledTimes(1);
});

test('Skeleton and SkeletonCard render', () => {
  const { getByTestId } = render(
    <>
      <Skeleton width={100} testID="sk-solo" />
      <SkeletonCard />
    </>
  );
  expect(getByTestId('sk-solo')).toBeTruthy();
  expect(getByTestId('skeleton-card')).toBeTruthy();
});

test('Card with onPress is pressable; plain Card renders content', () => {
  const onPress = jest.fn();
  const { getByTestId, queryByText } = render(
    <>
      <Card testID="card-press" onPress={onPress} elevated>
        <Text>card-a</Text>
      </Card>
      <Card testID="card-plain">
        <Text>card-b</Text>
      </Card>
    </>
  );
  expect(queryByText('card-a')).toBeTruthy();
  expect(queryByText('card-b')).toBeTruthy();
  fireEvent.click(getByTestId('card-press'));
  expect(onPress).toHaveBeenCalledTimes(1);
});

test('Button (spring press) fires onPress', () => {
  const onPress = jest.fn();
  const { getByTestId } = render(<Button label="확인" onPress={onPress} testID="btn" />);
  fireEvent.click(getByTestId('btn'));
  expect(onPress).toHaveBeenCalledTimes(1);
});

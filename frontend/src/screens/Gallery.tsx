/** 템플릿 갤러리 — 14종 응답 템플릿의 시각 카탈로그(데모/문서/스크린샷). */
import React from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Caption, Heading } from '../components/primitives';
import { MessageView } from '../components/message';
import { gallerySections } from '../fixtures/journeys';
import { color, space } from '../design/tokens';

export function Gallery() {
  return (
    <View style={styles.root} testID="screen-gallery">
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Caption>Samsung · AI 컨시어지</Caption>
          <Heading>응답 템플릿 갤러리</Heading>
        </View>
        <MessageView sections={gallerySections} onCta={() => {}} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  content: { padding: space.lg, maxWidth: 480, width: '100%', alignSelf: 'center' },
  header: { marginBottom: space.md },
});

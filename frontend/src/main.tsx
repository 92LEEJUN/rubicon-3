/** 웹 진입(react-native-web) — AppRegistry로 루트 마운트.
 *  쿼리: ?screen=home|support|chat|live|gallery|docs, ?ws=<bff ws>, ?api=<bff base>, ?token=<auth>,
 *        ?mock=1(BE 미연결 강제), ?reset=1(데모 상태 초기화). */
import React from 'react';
import { AppRegistry } from 'react-native';
import { App, type ScreenName } from './App';
import { mockStore } from './mock/store';

const SCREENS: ScreenName[] = ['home', 'support', 'chat', 'live', 'gallery', 'scenario', 'docs'];

function Root() {
  const params = new URLSearchParams(typeof location !== 'undefined' ? location.search : '');
  const raw = (params.get('screen') || 'home') as ScreenName;
  const screen = SCREENS.includes(raw) ? raw : 'home';
  const forceMock = params.get('mock') === '1';
  if (params.get('reset') === '1') mockStore.reset();
  // mock 강제면 api/ws를 비워 하위 계층(!base)이 mock으로 동작.
  const wsUrl = forceMock ? undefined : params.get('ws') || undefined;
  const apiBase = forceMock ? undefined : params.get('api') || undefined;
  const token = params.get('token') || undefined;
  const scenarioId = params.get('id') || undefined;
  return (
    <App
      initialScreen={screen}
      wsUrl={wsUrl}
      apiBase={apiBase}
      token={token}
      scenarioId={scenarioId}
    />
  );
}

AppRegistry.registerComponent('ConciergeApp', () => Root);
AppRegistry.runApplication('ConciergeApp', {
  rootTag: document.getElementById('root'),
});

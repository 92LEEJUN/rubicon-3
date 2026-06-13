/**
 * 채팅 트랜스포트 추상화(frontend-architecture §5) — UI/상태는 ChatTransport에만 의존.
 * 우선 구현 WebSocketTransport(→ BFF /chat). 테스트/스크린샷은 MockTransport.
 */
import type { Chunk, ClientMessage } from '../types/contract';

export interface ChatTransport {
  connect(): void | Promise<void>;
  send(message: ClientMessage): void;
  onChunk(handler: (c: Chunk) => void): void;
  onState(handler: (s: 'open' | 'closed' | 'error') => void): void;
  close(): void;
}

/** BFF WebSocket 구현(우선안). 인증 토큰은 헤더 또는 첫 메시지로(MVP는 서브프로토콜 생략). */
export class WebSocketTransport implements ChatTransport {
  private ws?: WebSocket;
  private chunkHandler: (c: Chunk) => void = () => {};
  private stateHandler: (s: 'open' | 'closed' | 'error') => void = () => {};
  private outbox: string[] = []; // OPEN 전 송신 보류 큐(자동 첫 질문 전송 대비)

  constructor(private url: string) {}

  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => {
      this.stateHandler('open');
      for (const data of this.outbox) this.ws!.send(data); // 보류분 플러시
      this.outbox = [];
    };
    this.ws.onclose = () => this.stateHandler('closed');
    this.ws.onerror = () => this.stateHandler('error');
    this.ws.onmessage = (e) => {
      try {
        this.chunkHandler(JSON.parse(String(e.data)));
      } catch {
        /* ignore */
      }
    };
  }
  send(message: ClientMessage) {
    const data = JSON.stringify(message);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(data);
    else this.outbox.push(data); // 아직 연결 전 — 열리면 보낸다
  }
  onChunk(h: (c: Chunk) => void) {
    this.chunkHandler = h;
  }
  onState(h: (s: 'open' | 'closed' | 'error') => void) {
    this.stateHandler = h;
  }
  close() {
    this.ws?.close();
  }
}

/**
 * 회복형 트랜스포트 — WS 우선, 연결 실패/타임아웃이면 조용히 Mock으로 폴백.
 * BE 미연결 상황에서도 에러를 노출하지 않고 예시 응답을 보여준다(graceful degradation).
 */
export class ResilientTransport implements ChatTransport {
  private ws: WebSocketTransport;
  private mock: MockTransport;
  private chunkHandler: (c: Chunk) => void = () => {};
  private stateHandler: (s: 'open' | 'closed' | 'error') => void = () => {};
  private sent: ClientMessage[] = [];
  private opened = false;
  private fellBack = false;
  private timer: ReturnType<typeof setTimeout> | undefined;

  constructor(
    url: string,
    mockScript: (m: ClientMessage) => Chunk[],
    private timeoutMs = 3500,
    mockOpts: { delayMs?: number } = {},
  ) {
    this.ws = new WebSocketTransport(url);
    this.mock = new MockTransport(mockScript, mockOpts); // 폴백 mock 스트리밍 효과(delayMs)
  }

  private fallback() {
    if (this.fellBack || this.opened) return;
    this.fellBack = true;
    if (this.timer) clearTimeout(this.timer);
    this.mock.onChunk((c) => this.chunkHandler(c));
    this.mock.onState(() => {}); // 폴백은 항상 "정상"처럼 보이게(에러 숨김)
    this.mock.connect();
    this.stateHandler('open');
    for (const m of this.sent) this.mock.send(m); // 보낸 메시지를 Mock으로 재생
  }

  connect() {
    this.ws.onChunk((c) => this.chunkHandler(c));
    this.ws.onState((s) => {
      if (this.fellBack) return;
      if (s === 'open') {
        this.opened = true;
        if (this.timer) clearTimeout(this.timer);
        this.stateHandler('open');
      } else if (!this.opened) this.fallback(); // error/closed before open → 폴백
    });
    this.ws.connect();
    this.timer = setTimeout(() => this.fallback(), this.timeoutMs); // 무응답 → 폴백
  }
  send(message: ClientMessage) {
    if (!this.fellBack) this.sent.push(message);
    (this.fellBack ? this.mock : this.ws).send(message);
  }
  onChunk(h: (c: Chunk) => void) {
    this.chunkHandler = h;
  }
  onState(h: (s: 'open' | 'closed' | 'error') => void) {
    this.stateHandler = h;
  }
  close() {
    if (this.timer) clearTimeout(this.timer);
    this.ws.close();
    this.mock.close();
  }
}

/** 스크립트된 청크를 재생하는 Mock(테스트·오프라인 스크린샷).
 *  opts.delayMs>0이면 청크를 **점진 방출**(스트리밍 효과) — delta는 글자 단위로 쪼갠다.
 *  기본 0이면 동기 방출(테스트 단언 안정). */
export class MockTransport implements ChatTransport {
  private chunkHandler: (c: Chunk) => void = () => {};
  private stateHandler: (s: 'open' | 'closed' | 'error') => void = () => {};
  private timer: ReturnType<typeof setTimeout> | undefined;

  constructor(
    private script: (message: ClientMessage) => Chunk[],
    private opts: { delayMs?: number } = {},
  ) {}

  connect() {
    this.stateHandler('open');
  }

  send(message: ClientMessage) {
    const chunks = this.script(message);
    const delay = this.opts.delayMs ?? 0;
    if (delay <= 0) {
      for (const c of chunks) this.chunkHandler(c);
      return;
    }
    const queue = this.expand(chunks);
    let i = 0;
    const tick = () => {
      if (i >= queue.length) return;
      this.chunkHandler(queue[i++]);
      if (i < queue.length) this.timer = setTimeout(tick, delay);
    };
    this.timer = setTimeout(tick, delay);
  }

  /** delta 청크를 글자(3자)로 쪼개 타이핑 효과를 낸다. 그 외 청크는 그대로. */
  private expand(chunks: Chunk[]): Chunk[] {
    const out: Chunk[] = [];
    for (const c of chunks) {
      if (c.type === 'delta' && c.text.length > 3) {
        for (let j = 0; j < c.text.length; j += 3)
          out.push({ type: 'delta', text: c.text.slice(j, j + 3) });
      } else {
        out.push(c);
      }
    }
    return out;
  }

  onChunk(h: (c: Chunk) => void) {
    this.chunkHandler = h;
  }
  onState(h: (s: 'open' | 'closed' | 'error') => void) {
    this.stateHandler = h;
  }
  close() {
    if (this.timer) clearTimeout(this.timer);
    this.stateHandler('closed');
  }
}

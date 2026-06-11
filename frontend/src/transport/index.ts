/**
 * 채팅 트랜스포트 추상화(frontend-architecture §5) — UI/상태는 ChatTransport에만 의존.
 * 우선 구현 WebSocketTransport(→ BFF /chat). 테스트/스크린샷은 MockTransport.
 */
import type { Chunk, ClientMessage } from "../types/contract";

export interface ChatTransport {
  connect(): void | Promise<void>;
  send(message: ClientMessage): void;
  onChunk(handler: (c: Chunk) => void): void;
  onState(handler: (s: "open" | "closed" | "error") => void): void;
  close(): void;
}

/** BFF WebSocket 구현(우선안). 인증 토큰은 헤더 또는 첫 메시지로(MVP는 서브프로토콜 생략). */
export class WebSocketTransport implements ChatTransport {
  private ws?: WebSocket;
  private chunkHandler: (c: Chunk) => void = () => {};
  private stateHandler: (s: "open" | "closed" | "error") => void = () => {};
  private outbox: string[] = []; // OPEN 전 송신 보류 큐(자동 첫 질문 전송 대비)

  constructor(private url: string) {}

  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => {
      this.stateHandler("open");
      for (const data of this.outbox) this.ws!.send(data); // 보류분 플러시
      this.outbox = [];
    };
    this.ws.onclose = () => this.stateHandler("closed");
    this.ws.onerror = () => this.stateHandler("error");
    this.ws.onmessage = (e) => {
      try { this.chunkHandler(JSON.parse(String(e.data))); } catch { /* ignore */ }
    };
  }
  send(message: ClientMessage) {
    const data = JSON.stringify(message);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(data);
    else this.outbox.push(data); // 아직 연결 전 — 열리면 보낸다
  }
  onChunk(h: (c: Chunk) => void) { this.chunkHandler = h; }
  onState(h: (s: "open" | "closed" | "error") => void) { this.stateHandler = h; }
  close() { this.ws?.close(); }
}

/** 스크립트된 청크를 재생하는 Mock(테스트·오프라인 스크린샷). */
export class MockTransport implements ChatTransport {
  private chunkHandler: (c: Chunk) => void = () => {};
  private stateHandler: (s: "open" | "closed" | "error") => void = () => {};

  constructor(private script: (message: ClientMessage) => Chunk[]) {}

  connect() { this.stateHandler("open"); }
  send(message: ClientMessage) {
    for (const c of this.script(message)) this.chunkHandler(c);
  }
  onChunk(h: (c: Chunk) => void) { this.chunkHandler = h; }
  onState(h: (s: "open" | "closed" | "error") => void) { this.stateHandler = h; }
  close() { this.stateHandler("closed"); }
}

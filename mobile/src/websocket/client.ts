/**
 * WebSocket client for the mobile viewer.
 *
 * Connects to /ws/viewer/{sessionId} and handles:
 * - Auto-reconnect with exponential backoff
 * - Message parsing and dispatch
 * - Connection state tracking
 */

export type ConnectionState = "connecting" | "connected" | "disconnected" | "error";

export interface WSCallbacks {
  onTranscript: (status: "partial" | "final", text: string) => void;
  onQuestion: (text: string, category?: string) => void;
  onAnswerStart: (question: string) => void;
  onAnswerDelta: (text: string) => void;
  onAnswerComplete: (question: string, fullText: string) => void;
  onStatus: (state: string, detail: string) => void;
  onConnectionChange: (state: ConnectionState) => void;
}

export class ViewerWSClient {
  private ws: WebSocket | null = null;
  private url: string;
  private callbacks: WSCallbacks;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectTimer: number | null = null;
  private intentionallyClosed = false;

  constructor(sessionId: string, callbacks: WSCallbacks) {
    // Determine WebSocket URL based on current location
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    this.url = `${protocol}//${host}/ws/viewer/${sessionId}`;
    this.callbacks = callbacks;
  }

  connect(): void {
    this.intentionallyClosed = false;
    this.callbacks.onConnectionChange("connecting");

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log("Viewer WebSocket connected");
        this.reconnectAttempts = 0;
        this.callbacks.onConnectionChange("connected");
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data);
          this.handleMessage(msg);
        } catch (e) {
          console.error("Failed to parse WS message:", e);
        }
      };

      this.ws.onclose = () => {
        console.log("Viewer WebSocket closed");
        if (!this.intentionallyClosed) {
          this.callbacks.onConnectionChange("disconnected");
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        this.callbacks.onConnectionChange("error");
      };
    } catch (e) {
      console.error("Failed to create WebSocket:", e);
      this.callbacks.onConnectionChange("error");
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    this.intentionallyClosed = true;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.callbacks.onConnectionChange("disconnected");
  }

  private handleMessage(msg: any): void {
    switch (msg.type) {
      case "transcript":
        this.callbacks.onTranscript(msg.status, msg.text);
        break;
      case "question":
        this.callbacks.onQuestion(msg.text, msg.category);
        break;
      case "answer_start":
        this.callbacks.onAnswerStart(msg.question);
        break;
      case "answer_delta":
        this.callbacks.onAnswerDelta(msg.text);
        break;
      case "answer_complete":
        this.callbacks.onAnswerComplete(msg.question, msg.full_text);
        break;
      case "status":
        this.callbacks.onStatus(msg.state, msg.detail);
        break;
      default:
        console.warn("Unknown WS message type:", msg.type);
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("Max reconnect attempts reached");
      this.callbacks.onConnectionChange("error");
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, delay);
  }
}

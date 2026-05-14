/**
 * SDD WebSocket Client — connects the frontend to the Python SDD agent server.
 */

import type { SDDClientMessage, SDDServerMessage } from './sdd-types';

export type SDDConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';

export interface SDDClientOptions {
  url: string;
  onMessage: (msg: SDDServerMessage) => void;
  onStatusChange: (status: SDDConnectionStatus) => void;
}

export class SDDClient {
  private ws: WebSocket | null = null;
  private url: string;
  private onMessage: (msg: SDDServerMessage) => void;
  private onStatusChange: (status: SDDConnectionStatus) => void;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private intentionalClose = false;

  constructor(options: SDDClientOptions) {
    this.url = options.url;
    this.onMessage = options.onMessage;
    this.onStatusChange = options.onStatusChange;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.intentionalClose = false;
    this.onStatusChange(this.reconnectAttempts > 0 ? 'reconnecting' : 'connecting');

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.onStatusChange('connected');
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as SDDServerMessage;
          this.onMessage(data);
        } catch (err) {
          console.error('[SDDClient] Failed to parse message:', err);
        }
      };

      this.ws.onclose = () => {
        if (!this.intentionalClose && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.onStatusChange('reconnecting');
          this.scheduleReconnect();
        } else {
          this.onStatusChange('disconnected');
        }
      };

      this.ws.onerror = () => {
        this.onStatusChange('error');
      };
    } catch {
      this.onStatusChange('error');
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.onStatusChange('disconnected');
  }

  send(msg: SDDClientMessage): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }
    this.ws.send(JSON.stringify(msg));
    return true;
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 10000);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}

import React from "react";
import { ConnectionState } from "../websocket/client";

interface Props {
  sessionId: string;
  connectionState: ConnectionState;
  backendState: string;
  backendStatus: string;
  tabTitle: string | null;
}

export default function StatusBar({
  sessionId,
  connectionState,
  backendState,
  backendStatus,
  tabTitle,
}: Props) {
  const isConnected = connectionState === "connected";
  const isListening = isConnected && backendState === "listening";

  const connectionText = {
    connecting: "Connecting...",
    connected: "Connected",
    disconnected: "Disconnected",
    error: "Connection Error",
  }[connectionState];

  const dotClass = {
    connecting: "dot-connecting",
    connected: "dot-connected",
    disconnected: "dot-disconnected",
    error: "dot-error",
  }[connectionState];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px 16px', background: 'rgba(10, 10, 26, 0.92)', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span className={`status-dot ${dotClass}`} />
        <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
          {connectionText}
        </span>
      </div>
      
      <div style={{ padding: '12px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border)', marginTop: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <span style={{ fontSize: '16px' }}>{isListening ? '🟢' : '⚪'}</span>
          <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
            {isListening ? "Listening" : "Not Listening"}
          </span>
        </div>
        
        <div style={{ fontSize: '13px', color: isListening ? 'var(--accent-blue)' : 'var(--text-muted)', marginLeft: '24px' }}>
            {isListening && tabTitle ? tabTitle : backendStatus}
        </div>

        {isConnected && (
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '12px', marginLeft: '24px', fontFamily: 'var(--font-mono)' }}>
            Session: {sessionId}
          </div>
        )}
      </div>
    </div>
  );
}

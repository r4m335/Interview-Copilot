import React from "react";
import { ConnectionState } from "../websocket/client";

interface Props {
  sessionId: string;
  connectionState: ConnectionState;
  backendStatus: string;
}

export default function StatusBar({
  sessionId,
  connectionState,
  backendStatus,
}: Props) {
  const statusText = {
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
    <header className="status-bar">
      <div className="status-bar-left">
        <span className="app-title">INTERVIEW AI</span>
        <span className="session-badge">{sessionId}</span>
      </div>
      <div className="status-bar-right">
        <span className={`status-dot ${dotClass}`} />
        <span className="status-label">{statusText}</span>
      </div>
    </header>
  );
}

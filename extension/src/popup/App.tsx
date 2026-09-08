import React, { useEffect, useState, useCallback } from "react";
import { QRCodeSVG } from "qrcode.react";

type CaptureStatus = "idle" | "capturing" | "stopped" | "error";

interface SessionInfo {
  sessionId: string;
  hostToken: string;
  viewerToken: string;
}

const BACKEND_URL = "http://localhost:8000";

export default function App() {
  const [status, setStatus] = useState<CaptureStatus>("idle");
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string>("");
  const [tabTitle, setTabTitle] = useState<string | null>(null);

  // Load stored session on mount
  useEffect(() => {
    // Check current capture status
    chrome.runtime.sendMessage({ type: "popup-status" }, (response) => {
      if (response?.isCapturing) {
        setStatus("capturing");
        if (response.tabTitle) {
          setTabTitle(response.tabTitle);
        }
        if (response.sessionId) {
          chrome.storage.local.get(
            ["sessionId", "hostToken", "viewerToken"],
            (result) => {
              if (result.sessionId) {
                setSession({
                  sessionId: result.sessionId,
                  hostToken: result.hostToken,
                  viewerToken: result.viewerToken,
                });
              }
            }
          );
        }
      } else {
        setStatus("idle");
      }
    });
  }, []);

  // Listen for status updates
  useEffect(() => {
    const listener = (message: any) => {
      if (message.type === "capture-status") {
        setStatus(message.status);
        if (message.tabTitle) {
          setTabTitle(message.tabTitle);
        }
        if (message.status === "stopped" || message.status === "error") {
          setTabTitle(null);
        }
        if (message.detail && message.status === "error") {
          setError(message.detail);
        }
      }
    };

    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  const handleStart = useCallback(() => {
    setError("");
    setStatus("capturing");
    chrome.runtime.sendMessage({ type: "popup-start" });
  }, []);

  const handleStop = useCallback(() => {
    chrome.runtime.sendMessage({ type: "popup-stop" });
    setStatus("stopped");
  }, []);

  const viewerUrl = session
    ? `${BACKEND_URL}/session/${session.sessionId}`
    : "";

  return (
    <div className="popup-container">
      <header className="popup-header">
        <h1>INTERVIEW COPILOT</h1>
        <div className={`status-dot ${status}`} />
      </header>

      <div className="popup-body">
        {/* Status */}
        <div className="status-text">
          {status === "idle" && "Not listening"}
          {status === "capturing" && "● Listening"}
          {status === "stopped" && "Not listening"}
          {status === "error" && `Error: ${error}`}
        </div>

        {/* Active Tab Info */}
        {status === "capturing" && tabTitle && (
          <div className="active-tab-info">
            <div className="info-label">Listening to:</div>
            <div className="info-value">{tabTitle}</div>
          </div>
        )}

        {/* Session info + QR code */}
        {session && status === "capturing" && (
          <div className="session-info">
            <div className="session-id">
              <div className="info-label" style={{textAlign: "center"}}>Session:</div>
              <strong>{session.sessionId}</strong>
            </div>

            <div className="qr-container">
              <QRCodeSVG
                value={viewerUrl}
                size={140}
                bgColor="transparent"
                fgColor="#e0e0e0"
                level="M"
              />
              <div className="qr-label">Scan with phone</div>
            </div>

            <div className="viewer-url">
              <a href={viewerUrl} target="_blank" rel="noopener">
                {viewerUrl}
              </a>
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="controls">
          {status !== "capturing" ? (
            <button className="btn-start" onClick={handleStart}>
              Start Listening
            </button>
          ) : (
            <button className="btn-stop" onClick={handleStop}>
              Stop Listening
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

import React, { useState } from "react";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import SessionPage from "./pages/SessionPage";

function LandingPage() {
  const [sessionId, setSessionId] = useState("");
  const navigate = useNavigate();

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault();
    if (sessionId.trim()) {
      navigate(`/session/${sessionId.trim()}`);
    }
  };

  return (
    <div className="landing">
      <h1>Interview Copilot</h1>
      <p>Scan the QR code from the extension to connect.</p>
      
      <div className="landing-divider">
        <span>OR</span>
      </div>

      <form onSubmit={handleJoin} className="manual-join-form">
        <input 
          type="text" 
          placeholder="Enter Session ID" 
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
          className="session-input"
        />
        <button type="submit" className="btn-join" disabled={!sessionId.trim()}>
          Join Session
        </button>
      </form>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/session/:sessionId" element={<SessionPage />} />
        <Route path="*" element={<LandingPage />} />
      </Routes>
    </BrowserRouter>
  );
}

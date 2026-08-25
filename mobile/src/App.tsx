import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import SessionPage from "./pages/SessionPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/session/:sessionId" element={<SessionPage />} />
        <Route
          path="*"
          element={
            <div className="landing">
              <h1>Interview Copilot</h1>
              <p>Scan the QR code from the extension to connect.</p>
            </div>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

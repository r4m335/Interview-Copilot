import React from "react";
import { useParams } from "react-router-dom";
import { useSession } from "../hooks/useSession";
import StatusBar from "../components/StatusBar";
import QuestionCard from "../components/QuestionCard";
import AnswerCard from "../components/AnswerCard";
import AnswerHistory from "../components/AnswerHistory";

export default function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  if (!sessionId) {
    return (
      <div className="error-page">
        <h1>Invalid Session</h1>
        <p>No session ID provided.</p>
      </div>
    );
  }

  const session = useSession(sessionId);

  return (
    <div className="session-page">
      <StatusBar
        sessionId={sessionId}
        connectionState={session.connectionState}
        backendStatus={session.backendStatus}
      />

      <main className="session-content">
        {/* Transcript indicator */}
        {session.transcript && session.transcriptStatus === "partial" && (
          <div className="transcript-indicator">
            <span className="transcript-dot">●</span>
            <span className="transcript-text">{session.transcript}</span>
          </div>
        )}

        {/* Current Q&A */}
        <QuestionCard question={session.currentQuestion} />
        <AnswerCard
          answer={session.currentAnswer}
          isStreaming={session.isAnswering}
        />

        {/* Waiting state */}
        {session.connectionState === "connected" &&
          !session.currentQuestion && (
            <div className="waiting-state">
              <div className="waiting-icon">🎧</div>
              <div className="waiting-text">Listening for questions...</div>
            </div>
          )}

        {/* History */}
        <AnswerHistory history={session.history} />
      </main>
    </div>
  );
}

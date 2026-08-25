import { useState, useEffect, useCallback, useRef } from "react";
import {
  ViewerWSClient,
  ConnectionState,
  WSCallbacks,
} from "../websocket/client";

export interface QAPair {
  question: string;
  answer: string;
  isComplete: boolean;
}

export interface SessionState {
  connectionState: ConnectionState;
  transcript: string;
  transcriptStatus: "partial" | "final" | "";
  currentQuestion: string;
  currentAnswer: string;
  isAnswering: boolean;
  backendStatus: string;
  history: QAPair[];
}

export function useSession(sessionId: string): SessionState {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const [transcript, setTranscript] = useState("");
  const [transcriptStatus, setTranscriptStatus] = useState<
    "partial" | "final" | ""
  >("");
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [isAnswering, setIsAnswering] = useState(false);
  const [backendStatus, setBackendStatus] = useState("");
  const [history, setHistory] = useState<QAPair[]>([]);

  const clientRef = useRef<ViewerWSClient | null>(null);

  useEffect(() => {
    const callbacks: WSCallbacks = {
      onConnectionChange: setConnectionState,

      onTranscript: (status, text) => {
        setTranscript(text);
        setTranscriptStatus(status);
      },

      onQuestion: (text) => {
        setCurrentQuestion(text);
        setCurrentAnswer("");
        setIsAnswering(false);
      },

      onAnswerStart: () => {
        setCurrentAnswer("");
        setIsAnswering(true);
      },

      onAnswerDelta: (text) => {
        setCurrentAnswer((prev) => prev + text);
      },

      onAnswerComplete: (question, fullText) => {
        setCurrentAnswer(fullText);
        setIsAnswering(false);

        // Add to history
        setHistory((prev) => [
          { question, answer: fullText, isComplete: true },
          ...prev,
        ]);
      },

      onStatus: (_state, detail) => {
        setBackendStatus(detail);
      },
    };

    const client = new ViewerWSClient(sessionId, callbacks);
    clientRef.current = client;
    client.connect();

    return () => {
      client.disconnect();
      clientRef.current = null;
    };
  }, [sessionId]);

  return {
    connectionState,
    transcript,
    transcriptStatus,
    currentQuestion,
    currentAnswer,
    isAnswering,
    backendStatus,
    history,
  };
}

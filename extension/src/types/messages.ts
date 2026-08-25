/**
 * TypeScript interfaces for inter-component messaging
 * within the Chrome extension.
 */

// --- Extension internal messages ---

export interface StartCaptureMessage {
  type: "start-capture";
  streamId: string;
  sessionId: string;
  serverUrl: string;
}

export interface StopCaptureMessage {
  type: "stop-capture";
}

export interface CaptureStatusMessage {
  type: "capture-status";
  status: "capturing" | "stopped" | "error";
  detail?: string;
}

export interface MeetingDetectedMessage {
  type: "meeting-detected";
  platform: "google-meet" | "teams" | "zoom" | "unknown";
  url: string;
}

export interface SessionCreatedMessage {
  type: "session-created";
  sessionId: string;
  hostToken: string;
  viewerToken: string;
}

export type ExtensionMessage =
  | StartCaptureMessage
  | StopCaptureMessage
  | CaptureStatusMessage
  | MeetingDetectedMessage
  | SessionCreatedMessage;

// --- WebSocket messages from backend ---

export interface TranscriptWsMessage {
  type: "transcript";
  status: "partial" | "final";
  text: string;
  timestamp?: number;
}

export interface QuestionWsMessage {
  type: "question";
  text: string;
  category?: string;
}

export interface AnswerStartWsMessage {
  type: "answer_start";
  question: string;
}

export interface AnswerDeltaWsMessage {
  type: "answer_delta";
  text: string;
}

export interface AnswerCompleteWsMessage {
  type: "answer_complete";
  question: string;
  full_text: string;
}

export interface StatusWsMessage {
  type: "status";
  state: string;
  detail: string;
}

export type BackendWsMessage =
  | TranscriptWsMessage
  | QuestionWsMessage
  | AnswerStartWsMessage
  | AnswerDeltaWsMessage
  | AnswerCompleteWsMessage
  | StatusWsMessage;

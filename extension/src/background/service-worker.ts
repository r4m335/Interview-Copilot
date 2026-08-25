/**
 * Service worker — extension lifecycle manager.
 *
 * Responsibilities:
 * - Handle popup commands (start/stop capture)
 * - Manage the offscreen document lifecycle
 * - Get tabCapture stream IDs
 * - Relay messages between popup and offscreen document
 * - Create sessions via backend API
 */

const OFFSCREEN_URL = "src/offscreen/offscreen.html";
const BACKEND_URL = "http://localhost:8000";

let currentSessionId: string | null = null;
let isCapturing = false;

// --- Offscreen document management ---

async function ensureOffscreenDocument(): Promise<void> {
  // Check if offscreen doc already exists
  const existingContexts = await chrome.runtime.getContexts({
    contextTypes: [chrome.runtime.ContextType.OFFSCREEN_DOCUMENT],
  });

  if (existingContexts.length > 0) {
    return; // Already exists
  }

  await chrome.offscreen.createDocument({
    url: OFFSCREEN_URL,
    reasons: [chrome.offscreen.Reason.USER_MEDIA],
    justification: "Capture tab audio for real-time transcription",
  });
}

async function closeOffscreenDocument(): Promise<void> {
  try {
    await chrome.offscreen.closeDocument();
  } catch {
    // Already closed — ignore
  }
}

// --- Session management ---

async function createSession(): Promise<{
  sessionId: string;
  hostToken: string;
  viewerToken: string;
}> {
  const response = await fetch(`${BACKEND_URL}/api/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Failed to create session: ${response.statusText}`);
  }

  const data = await response.json();
  return {
    sessionId: data.session_id,
    hostToken: data.host_token,
    viewerToken: data.viewer_token,
  };
}

// --- Tab capture ---

async function startCapture(): Promise<void> {
  if (isCapturing) {
    console.warn("Already capturing");
    return;
  }

  try {
    // 1. Create a session
    const session = await createSession();
    currentSessionId = session.sessionId;

    // Store session info
    await chrome.storage.local.set({
      sessionId: session.sessionId,
      hostToken: session.hostToken,
      viewerToken: session.viewerToken,
    });

    // 2. Get the active tab
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });

    if (!tab?.id) {
      throw new Error("No active tab found");
    }

    // 3. Get media stream ID for the tab
    const streamId = await new Promise<string>((resolve, reject) => {
      chrome.tabCapture.getMediaStreamId(
        { targetTabId: tab.id },
        (id) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(id);
          }
        }
      );
    });

    // 4. Create offscreen document
    await ensureOffscreenDocument();

    // 5. Send capture command to offscreen document
    chrome.runtime.sendMessage({
      type: "start-capture",
      streamId,
      sessionId: session.sessionId,
      serverUrl: BACKEND_URL,
    });

    isCapturing = true;

    // Notify popup
    chrome.runtime.sendMessage({
      type: "capture-status",
      status: "capturing",
      detail: `Session: ${session.sessionId}`,
    });

    console.log(`Capture started — session: ${session.sessionId}`);
  } catch (error) {
    console.error("Failed to start capture:", error);
    chrome.runtime.sendMessage({
      type: "capture-status",
      status: "error",
      detail: String(error),
    });
  }
}

async function stopCapture(): Promise<void> {
  try {
    chrome.runtime.sendMessage({ type: "stop-capture" });
    await closeOffscreenDocument();
    isCapturing = false;
    currentSessionId = null;

    chrome.runtime.sendMessage({
      type: "capture-status",
      status: "stopped",
    });

    console.log("Capture stopped");
  } catch (error) {
    console.error("Failed to stop capture:", error);
  }
}

// --- Message handling ---

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  switch (message.type) {
    case "popup-start":
      startCapture().then(() => sendResponse({ ok: true }));
      return true; // Async response

    case "popup-stop":
      stopCapture().then(() => sendResponse({ ok: true }));
      return true;

    case "popup-status":
      sendResponse({
        isCapturing,
        sessionId: currentSessionId,
      });
      return false;

    case "capture-status":
      // Relay from offscreen to popup — just let it propagate
      return false;
  }
});

console.log("Interview Copilot service worker loaded");

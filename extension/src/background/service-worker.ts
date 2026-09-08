/**
 * Service worker — extension lifecycle manager.
 */

const OFFSCREEN_URL = "src/offscreen/offscreen.html";
const BACKEND_URL = "http://localhost:8000";

// --- Offscreen document management ---

async function hasOffscreenDocument(): Promise<boolean> {
  const existingContexts = await chrome.runtime.getContexts({
    contextTypes: [chrome.runtime.ContextType.OFFSCREEN_DOCUMENT],
  });
  return existingContexts.length > 0;
}

async function ensureOffscreenDocument(): Promise<void> {
  if (await hasOffscreenDocument()) {
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

async function createSession(tabTitle: string): Promise<{
  sessionId: string;
  hostToken: string;
  viewerToken: string;
}> {
  const response = await fetch(`${BACKEND_URL}/api/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tab_title: tabTitle }),
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
  try {
    // Check actual offscreen state
    const currentlyCapturing = await hasOffscreenDocument();

    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });

    if (!tab?.id) {
      throw new Error("No active tab found");
    }

    if (currentlyCapturing) {
      const { capturedTabId } = await chrome.storage.local.get(["capturedTabId"]);
      if (capturedTabId === tab.id) {
        console.warn("Already capturing this tab");
        return;
      } else {
        console.log("Switching capture to new tab");
        await stopCapture();
      }
    }

    // 1. Create a session
    const session = await createSession(tab.title || "Unknown Tab");

    // Store session info
    await chrome.storage.local.set({
      sessionId: session.sessionId,
      hostToken: session.hostToken,
      viewerToken: session.viewerToken,
      capturedTabId: tab.id,
      capturedTabTitle: tab.title || "Unknown Tab",
    });

    // 2. Get media stream ID for the tab
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

    // 3. Create offscreen document
    await ensureOffscreenDocument();

    // 4. Send capture command to offscreen document
    chrome.runtime.sendMessage({
      type: "start-capture",
      streamId,
      sessionId: session.sessionId,
      serverUrl: BACKEND_URL,
    });

    // Notify popup
    chrome.runtime.sendMessage({
      type: "capture-status",
      status: "capturing",
      detail: `Session: ${session.sessionId}`,
      tabTitle: tab.title || "Unknown Tab",
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
    
    await chrome.storage.local.remove(["capturedTabId", "capturedTabTitle"]);

    chrome.runtime.sendMessage({
      type: "capture-status",
      status: "stopped",
    });

    console.log("Capture stopped");
  } catch (error) {
    console.error("Failed to stop capture:", error);
  }
}

async function getCaptureStatus(): Promise<any> {
  const isCapturing = await hasOffscreenDocument();
  if (!isCapturing) {
    // Cleanup stale storage if offscreen document is dead
    await chrome.storage.local.remove(["capturedTabId", "capturedTabTitle"]);
    return { isCapturing: false, sessionId: null, tabTitle: null };
  }
  
  const storage = await chrome.storage.local.get(["sessionId", "capturedTabTitle"]);
  return {
    isCapturing: true,
    sessionId: storage.sessionId || null,
    tabTitle: storage.capturedTabTitle || "Unknown Tab",
  };
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
      getCaptureStatus().then(sendResponse);
      return true; // Async response

    case "capture-status":
      // Relay from offscreen to popup — just let it propagate
      return false;

    case "offscreen-stopped":
      stopCapture();
      return false;
  }
});

console.log("Interview Copilot service worker loaded");

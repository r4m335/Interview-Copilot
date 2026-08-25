/**
 * Content script — detects meeting platforms.
 *
 * Injected into Google Meet, Teams, and Zoom pages.
 * Notifies the service worker when a meeting is detected.
 */

function detectPlatform():
  | "google-meet"
  | "teams"
  | "zoom"
  | "unknown" {
  const url = window.location.href;

  if (url.includes("meet.google.com")) return "google-meet";
  if (url.includes("teams.microsoft.com")) return "teams";
  if (url.includes("zoom.us")) return "zoom";

  return "unknown";
}

function notifyMeetingDetected(): void {
  const platform = detectPlatform();

  if (platform !== "unknown") {
    chrome.runtime.sendMessage({
      type: "meeting-detected",
      platform,
      url: window.location.href,
    });

    console.log(`[Interview Copilot] Meeting detected: ${platform}`);
  }
}

// Detect on load
notifyMeetingDetected();

// Also detect on URL changes (SPA navigation)
let lastUrl = window.location.href;
const observer = new MutationObserver(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    notifyMeetingDetected();
  }
});

observer.observe(document.body, { childList: true, subtree: true });

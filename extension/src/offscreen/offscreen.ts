/**
 * Offscreen document — processes tab audio.
 *
 * Flow:
 * 1. Receives streamId from service worker
 * 2. Gets MediaStream via getUserMedia
 * 3. Creates AudioContext → AudioWorkletNode
 * 4. Worklet downsamples to 16kHz mono PCM16
 * 5. Energy-based VAD filters silence
 * 6. Speech frames sent to backend via WebSocket
 * 7. Tab audio remains audible (connected to destination)
 */

import { StartCaptureMessage } from "../types/messages";

let audioContext: AudioContext | null = null;
let mediaStream: MediaStream | null = null;
let wsClient: WebSocket | null = null;
let sequenceNumber = 0;

// --- Audio processing ---

async function startCapture(
  streamId: string,
  sessionId: string,
  serverUrl: string
): Promise<void> {
  try {
    // 1. Get the MediaStream from the tab
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: {
          chromeMediaSource: "tab",
          chromeMediaSourceId: streamId,
        },
      } as any,
      video: false,
    });

    // 2. Create AudioContext
    audioContext = new AudioContext({ sampleRate: 48000 });
    const source = audioContext.createMediaStreamSource(mediaStream);

    // Keep tab audio audible
    source.connect(audioContext.destination);

    // 3. Connect WebSocket to backend
    const wsUrl = serverUrl.replace("http", "ws") + `/ws/host/${sessionId}`;
    wsClient = new WebSocket(wsUrl);

    wsClient.onopen = () => {
      console.log("WebSocket connected to backend");
      chrome.runtime.sendMessage({
        type: "capture-status",
        status: "capturing",
        detail: "Connected to backend",
      });
    };

    wsClient.onerror = (e) => {
      console.error("WebSocket error:", e);
      chrome.runtime.sendMessage({ type: "offscreen-stopped" });
      chrome.runtime.sendMessage({
        type: "capture-status",
        status: "error",
        detail: "WebSocket connection failed",
      });
    };

    wsClient.onclose = () => {
      console.log("WebSocket closed");
      chrome.runtime.sendMessage({ type: "offscreen-stopped" });
    };

    // 4. Use AudioWorkletNode for modern, non-blocking audio processing
    const workletUrl = chrome.runtime.getURL('audio-processor.js');
    await audioContext.audioWorklet.addModule(workletUrl);
    const workletNode = new AudioWorkletNode(audioContext, 'vad-processor');

    workletNode.port.onmessage = (event: MessageEvent) => {
      const data = event.data;
      if (data.event === 'speech_start') {
        console.log("Speech started");
      } else if (data.event === 'speech_end') {
        console.log("Speech ended");
        sendControlFrame("speech_end");
      } else if (data.event === 'audio_data') {
        sendAudioFrame(data.buffer);
      } else if (data instanceof ArrayBuffer) {
        sendAudioFrame(data);
      }
    };

    source.connect(workletNode);
    workletNode.connect(audioContext.destination);

    console.log("Audio capture started via AudioWorklet");
  } catch (error) {
    console.error("Failed to start audio capture:", error);
    chrome.runtime.sendMessage({
      type: "capture-status",
      status: "error",
      detail: String(error),
    });
  }
}

function sendAudioFrame(pcmBuffer: ArrayBuffer): void {
  if (!wsClient || wsClient.readyState !== WebSocket.OPEN) {
    return;
  }

  // Build frame: [4B sequence][4B timestamp][PCM data]
  const header = new ArrayBuffer(8);
  const headerView = new DataView(header);
  headerView.setUint32(0, sequenceNumber++, true); // Little-endian
  headerView.setUint32(4, Date.now() & 0xffffffff, true);

  // Concatenate header + PCM data
  const frame = new Uint8Array(header.byteLength + pcmBuffer.byteLength);
  frame.set(new Uint8Array(header), 0);
  frame.set(new Uint8Array(pcmBuffer), header.byteLength);

  wsClient.send(frame.buffer);
}

function sendControlFrame(controlType: string): void {
  if (!wsClient || wsClient.readyState !== WebSocket.OPEN) {
    return;
  }

  const encoder = new TextEncoder();
  const controlBytes = encoder.encode(controlType);
  
  const header = new ArrayBuffer(8);
  const headerView = new DataView(header);
  headerView.setUint32(0, 0xFFFFFFFF, true); // Control frame marker
  headerView.setUint32(4, Date.now() & 0xffffffff, true);

  const frame = new Uint8Array(header.byteLength + controlBytes.byteLength);
  frame.set(new Uint8Array(header), 0);
  frame.set(controlBytes, header.byteLength);

  wsClient.send(frame.buffer);
}

function stopCapture(): void {
  if (wsClient) {
    wsClient.close();
    wsClient = null;
  }

  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }

  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }

  sequenceNumber = 0;

  console.log("Audio capture stopped");
}

// --- Message handling ---

chrome.runtime.onMessage.addListener((message: any) => {
  switch (message.type) {
    case "start-capture": {
      const msg = message as StartCaptureMessage;
      startCapture(msg.streamId, msg.sessionId, msg.serverUrl);
      break;
    }
    case "stop-capture":
      stopCapture();
      break;
  }
});

console.log("Offscreen document loaded");

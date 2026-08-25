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

// --- VAD parameters ---
const VAD_ENERGY_THRESHOLD = 0.005; // RMS energy threshold for speech detection
const VAD_PRE_ROLL_FRAMES = 4; // ~200ms at 50ms per frame
const VAD_POST_ROLL_FRAMES = 10; // ~500ms at 50ms per frame

let vadSpeechFrames = 0; // Consecutive frames above threshold
let vadSilenceFrames = 0; // Consecutive frames below threshold
let vadIsSpeaking = false;
let vadPreRollBuffer: ArrayBuffer[] = [];

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
      chrome.runtime.sendMessage({
        type: "capture-status",
        status: "error",
        detail: "WebSocket connection failed",
      });
    };

    wsClient.onclose = () => {
      console.log("WebSocket closed");
    };

    // 4. Use ScriptProcessorNode for audio processing
    // (AudioWorklet would be ideal but requires separate file loading
    // which is complex in an offscreen document — using ScriptProcessor
    // for V1 simplicity, will migrate to AudioWorklet in V2)
    const bufferSize = 4096;
    const processor = audioContext.createScriptProcessor(bufferSize, 1, 1);

    // Downsample ratio: 48000 → 16000 (3:1)
    const DOWNSAMPLE_RATIO = 3;
    const TARGET_SAMPLE_RATE = 16000;

    processor.onaudioprocess = (event: AudioProcessingEvent) => {
      const inputData = event.inputBuffer.getChannelData(0);

      // Downsample 48kHz → 16kHz (simple decimation)
      const downsampled = new Float32Array(
        Math.floor(inputData.length / DOWNSAMPLE_RATIO)
      );
      for (let i = 0; i < downsampled.length; i++) {
        downsampled[i] = inputData[i * DOWNSAMPLE_RATIO];
      }

      // Calculate RMS energy for VAD
      let sumSquares = 0;
      for (let i = 0; i < downsampled.length; i++) {
        sumSquares += downsampled[i] * downsampled[i];
      }
      const rms = Math.sqrt(sumSquares / downsampled.length);

      // Convert to PCM16
      const pcm16 = new Int16Array(downsampled.length);
      for (let i = 0; i < downsampled.length; i++) {
        const s = Math.max(-1, Math.min(1, downsampled[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      // VAD: energy-based with pre-roll / post-roll
      const isSpeech = rms > VAD_ENERGY_THRESHOLD;

      if (isSpeech) {
        vadSpeechFrames++;
        vadSilenceFrames = 0;

        if (!vadIsSpeaking && vadSpeechFrames >= 2) {
          // Speech started — send pre-roll buffer first
          vadIsSpeaking = true;
          for (const preRollFrame of vadPreRollBuffer) {
            sendAudioFrame(preRollFrame);
          }
          vadPreRollBuffer = [];
        }

        if (vadIsSpeaking) {
          sendAudioFrame(pcm16.buffer);
        }
      } else {
        vadSpeechFrames = 0;
        vadSilenceFrames++;

        if (vadIsSpeaking) {
          // Post-roll: keep sending for a bit after speech ends
          if (vadSilenceFrames <= VAD_POST_ROLL_FRAMES) {
            sendAudioFrame(pcm16.buffer);
          } else {
            vadIsSpeaking = false;
          }
        } else {
          // Pre-roll: keep a rolling buffer of recent silence
          vadPreRollBuffer.push(pcm16.buffer.slice(0));
          if (vadPreRollBuffer.length > VAD_PRE_ROLL_FRAMES) {
            vadPreRollBuffer.shift();
          }
        }
      }
    };

    source.connect(processor);
    processor.connect(audioContext.destination);

    console.log("Audio capture started");
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
  vadIsSpeaking = false;
  vadSpeechFrames = 0;
  vadSilenceFrames = 0;
  vadPreRollBuffer = [];

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

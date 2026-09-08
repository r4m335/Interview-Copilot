class VADProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 4096;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
    this.DOWNSAMPLE_RATIO = 3; // 48kHz to 16kHz
    
    // VAD settings
    this.isSpeaking = false;
    this.silenceCounter = 0;
    this.SILENCE_CHUNKS = 20; // ~1.7s of silence
    this.RMS_THRESHOLD = 0.001;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    
    const inputData = input[0];
    for (let i = 0; i < inputData.length; i++) {
      this.buffer[this.bufferIndex++] = inputData[i];
      if (this.bufferIndex >= this.bufferSize) {
        this.processChunk(this.buffer);
        this.bufferIndex = 0;
      }
    }
    return true;
  }

  processChunk(chunk) {
    // Calculate RMS for VAD
    let sumSquares = 0;
    for (let i = 0; i < chunk.length; i++) {
      sumSquares += chunk[i] * chunk[i];
    }
    const rms = Math.sqrt(sumSquares / chunk.length);

    if (rms > this.RMS_THRESHOLD) {
      if (!this.isSpeaking) {
        this.isSpeaking = true;
        this.port.postMessage({ event: 'speech_start' });
      }
      this.silenceCounter = 0;
    } else {
      if (this.isSpeaking) {
        this.silenceCounter++;
        if (this.silenceCounter >= this.SILENCE_CHUNKS) {
          this.isSpeaking = false;
          this.silenceCounter = 0;
          this.port.postMessage({ event: 'speech_end' });
          // Don't send this chunk, we are now silent
          return;
        }
      } else {
        // Not speaking, ignore audio
        return;
      }
    }

    // Downsample 48kHz -> 16kHz
    const downsampledLength = Math.floor(chunk.length / this.DOWNSAMPLE_RATIO);
    const downsampled = new Float32Array(downsampledLength);
    for (let i = 0; i < downsampled.length; i++) {
      downsampled[i] = chunk[i * this.DOWNSAMPLE_RATIO];
    }

    // Convert to PCM16
    const pcm16 = new Int16Array(downsampled.length);
    for (let i = 0; i < downsampled.length; i++) {
      const s = Math.max(-1, Math.min(1, downsampled[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    this.port.postMessage({ event: 'audio_data', buffer: pcm16.buffer }, [pcm16.buffer]);
  }
}

registerProcessor('vad-processor', VADProcessor);

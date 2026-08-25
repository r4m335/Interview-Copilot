"""Ring buffer for accumulating PCM audio chunks."""

from __future__ import annotations

import numpy as np

from app.config import settings


class AudioBuffer:
    """
    Accumulates incoming PCM16 audio data into a rolling buffer.

    The buffer stores up to `max_seconds` of audio. When full, old
    data is discarded (ring behavior). Provides methods to retrieve
    the accumulated audio for ASR processing.
    """

    def __init__(self, max_seconds: float = 30.0) -> None:
        self.sample_rate = settings.sample_rate
        self.max_samples = int(max_seconds * self.sample_rate)
        self._buffer = np.zeros(self.max_samples, dtype=np.float32)
        self._write_pos = 0
        self._total_samples = 0

    def add_pcm16(self, data: bytes) -> int:
        """
        Add raw PCM16 (little-endian, mono, 16kHz) bytes to the buffer.

        Returns the number of samples added.
        """
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        n = len(samples)

        if n >= self.max_samples:
            # Data larger than buffer — keep only the last max_samples
            self._buffer[:] = samples[-self.max_samples :]
            self._write_pos = 0
            self._total_samples = self.max_samples
        elif self._write_pos + n <= self.max_samples:
            # Fits without wrapping
            self._buffer[self._write_pos : self._write_pos + n] = samples
            self._write_pos += n
            self._total_samples = min(self._total_samples + n, self.max_samples)
        else:
            # Wraps around
            first = self.max_samples - self._write_pos
            self._buffer[self._write_pos :] = samples[:first]
            self._buffer[: n - first] = samples[first:]
            self._write_pos = n - first
            self._total_samples = self.max_samples

        return n

    def get_audio(self, last_seconds: float | None = None) -> np.ndarray:
        """
        Get audio data from the buffer.

        If last_seconds is given, return only the most recent N seconds.
        Otherwise return all accumulated audio.
        """
        if self._total_samples == 0:
            return np.zeros(0, dtype=np.float32)

        if last_seconds is not None:
            n = min(int(last_seconds * self.sample_rate), self._total_samples)
        else:
            n = self._total_samples

        if self._total_samples < self.max_samples:
            # Buffer hasn't wrapped yet
            return self._buffer[max(0, self._write_pos - n) : self._write_pos].copy()
        else:
            # Buffer has wrapped — need to reconstruct order
            start = (self._write_pos - n) % self.max_samples
            if start < self._write_pos:
                return self._buffer[start : self._write_pos].copy()
            else:
                return np.concatenate(
                    [self._buffer[start:], self._buffer[: self._write_pos]]
                )

    def clear(self) -> None:
        """Reset the buffer."""
        self._buffer[:] = 0
        self._write_pos = 0
        self._total_samples = 0

    @property
    def duration_seconds(self) -> float:
        """Current amount of audio in the buffer, in seconds."""
        return self._total_samples / self.sample_rate

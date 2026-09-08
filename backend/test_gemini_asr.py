import os
import wave
import io
from dotenv import load_dotenv
import numpy as np

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

try:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    USE_GENAI = True
except ImportError:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    USE_GENAI = False

def create_wav(pcm_data: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes((pcm_data * 32767).astype(np.int16).tobytes())
    return buf.getvalue()

# Create 2 seconds of dummy audio (sine wave)
t = np.linspace(0, 2, 16000 * 2)
audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
wav_bytes = create_wav(audio)

print(f"Using google.genai: {USE_GENAI}")
print("Calling Gemini 3.5 Transcribe...")

try:
    if USE_GENAI:
        response = client.models.generate_content(
            model='gemini-3.5-transcribe',
            contents=[types.Part.from_bytes(data=wav_bytes, mime_type='audio/wav')]
        )
        print(f"Response: {response.candidates[0]}")
    else:
        model = genai.GenerativeModel('gemini-3.5-transcribe')
        response = model.generate_content([
            {"mime_type": "audio/wav", "data": wav_bytes}
        ])
        print(f"Response: {response.candidates[0]}")
except Exception as e:
    print(f"Error: {e}")

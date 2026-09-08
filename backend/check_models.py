import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("No GEMINI_API_KEY found")
    exit(1)

genai.configure(api_key=api_key)

print("Listing models...")
try:
    models = list(genai.list_models())
    transcribe_models = [m.name for m in models if 'transcribe' in m.name.lower() or 'gemini-3.5' in m.name.lower()]
    print("Transcribe or 3.5 models found:")
    for m in transcribe_models:
        print(m)
    
    if not transcribe_models:
        print("No matching models found.")
except Exception as e:
    print(f"Error: {e}")

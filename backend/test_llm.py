import asyncio
from app.llm.client import llm_client
from app.llm.prompts import SYSTEM_PROMPT

async def main():
    print("Testing LLM generation...")
    try:
        response = await llm_client.generate("What is polymorphism?", SYSTEM_PROMPT)
        print(f"Success! Response: {response}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())

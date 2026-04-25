"""
NVIDIA AI Client — wraps OpenAI-compatible API
Model: meta/llama-3.3-70b-instruct (best for reasoning + tool-like behavior)
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_nvidia_client() -> OpenAI:
    return OpenAI(
        base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        api_key=os.getenv("NVIDIA_API_KEY"),
    )

MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")


def chat_completion(messages: list[dict], system_prompt: str = None, temperature: float = 0.4) -> str:
    """Single completion call to NVIDIA API."""
    client = get_nvidia_client()

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    response = client.chat.completions.create(
        model=MODEL,
        messages=full_messages,
        temperature=temperature,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()
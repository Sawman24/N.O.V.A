import os
from openai import OpenAI
from .base import BaseBackend


class LocalBackend(BaseBackend):
    """
    Generic adapter for any local OpenAI-compatible server.
    Works with LM Studio, Jan, vLLM, KoboldCPP, llama.cpp server, etc.
    """
    NAME = "local"

    def __init__(self):
        base_url = os.getenv("LOCAL_BASE_URL", "http://localhost:1234/v1")
        api_key = os.getenv("LOCAL_API_KEY", "local")
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = os.getenv("AGENT_MODEL", "local-model")
        print(f"[Nova] Backend: Local ({base_url}) — {self.model}")

    def chat(self, messages: list, tools: list):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools if tools else None,
        )
        return response.choices[0].message

    def get_info(self) -> dict:
        return {"backend": self.NAME, "model": self.model}

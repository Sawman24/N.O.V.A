import os
from openai import OpenAI
from .base import BaseBackend


class OllamaBackend(BaseBackend):
    NAME = "ollama"

    def __init__(self):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self._default_model = os.getenv("AGENT_MODEL", "qwen2.5:7b")
        print(f"[Nova] Backend: Ollama — default model: {self._default_model}")

    def chat(self, messages: list, tools: list):
        # Read model fresh each call so switching models needs no restart
        model = os.getenv("AGENT_MODEL", self._default_model)
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools if tools else None,
        )
        return response.choices[0].message

    def get_info(self) -> dict:
        return {"backend": self.NAME, "model": os.getenv("AGENT_MODEL", self._default_model)}

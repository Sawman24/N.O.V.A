from abc import ABC, abstractmethod
from typing import Generator


class BaseBackend(ABC):
    @abstractmethod
    def chat(self, messages: list, tools: list):
        """
        Send messages to the local AI model.
        Returns an OpenAI-compatible message object with .content and .tool_calls.
        """
        pass

    @abstractmethod
    def chat_stream(self, messages: list, tools: list) -> Generator:
        """
        Stream a response from the local AI model.
        Yields OpenAI-compatible chunk objects from the streaming API.
        """
        pass

    @abstractmethod
    def get_info(self) -> dict:
        """Return backend name and active model for display in the UI."""
        pass

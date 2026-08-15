import os
import json
from abc import ABC, abstractmethod
from typing import Generator

CONFIG_PATH = "profiles/config.json"


def get_config_val(key: str, default: any = "") -> any:
    """
    Fetch configuration from persistent profiles/config.json file (which is inside
    a mounted volume) falling back to environment variables.
    """
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
                if key in config:
                    val = config[key]
                    if isinstance(default, int) and not isinstance(val, int):
                        return int(val)
                    if isinstance(default, float) and not isinstance(val, float):
                        return float(val)
                    if isinstance(default, bool) and not isinstance(val, bool):
                        return str(val).lower().strip() in ("true", "1", "yes")
                    return val
        except Exception:
            pass
    val = os.getenv(key)
    if val is not None:
        if isinstance(default, int):
            return int(val)
        if isinstance(default, float):
            return float(val)
        if isinstance(default, bool):
            return str(val).lower().strip() in ("true", "1", "yes")
        return val
    return default


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

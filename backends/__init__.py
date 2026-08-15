import os
from .base import BaseBackend
from nova_logging import get_logger

logger = get_logger("backends")


class ErrorBackend(BaseBackend):
    """
    Fallback backend returned when the primary backend fails to initialize.
    Allows the FastAPI server to start successfully so the user can use the
    Web UI to configure settings and download models.
    """
    def __init__(self, error_msg: str):
        self.error_msg = error_msg

    def chat(self, messages: list, tools: list):
        raise RuntimeError(self.error_msg)

    def chat_stream(self, messages: list, tools: list):
        # A simple generator that yields a single error event
        yield {"type": "error", "content": self.error_msg}

    def get_info(self) -> dict:
        # Truncate long error messages for UI display
        display_err = self.error_msg
        if len(display_err) > 40:
            display_err = display_err[:37] + "..."
        return {"backend": "error", "model": display_err}


def get_backend() -> BaseBackend:
    """
    Factory function — reads BACKEND env var and returns the right adapter.
    Supported values: 'ollama' (default), 'local', 'huggingface'
    """
    try:
        backend_type = os.getenv("BACKEND", "ollama").lower().strip()

        if backend_type == "ollama":
            from .ollama import OllamaBackend
            return OllamaBackend()
        elif backend_type == "local":
            from .local import LocalBackend
            return LocalBackend()
        elif backend_type == "huggingface":
            from .huggingface import HuggingFaceBackend
            return HuggingFaceBackend()
        else:
            logger.warning(f"Unknown backend '{backend_type}' — falling back to Ollama.")
            from .ollama import OllamaBackend
            return OllamaBackend()
    except Exception as e:
        err_msg = f"Failed to initialize backend: {e}"
        logger.error(err_msg)
        return ErrorBackend(err_msg)

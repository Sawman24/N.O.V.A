import os
from .base import BaseBackend
from nova_logging import get_logger

logger = get_logger("backends")


def get_backend() -> BaseBackend:
    """
    Factory function — reads BACKEND env var and returns the right adapter.
    Supported values: 'ollama' (default), 'local', 'huggingface'
    """
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

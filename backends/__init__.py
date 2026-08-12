import os
from .base import BaseBackend


def get_backend() -> BaseBackend:
    """
    Factory function — reads BACKEND env var and returns the right adapter.
    Supported values: 'ollama' (default), 'local'
    """
    backend_type = os.getenv("BACKEND", "ollama").lower().strip()

    if backend_type == "ollama":
        from .ollama import OllamaBackend
        return OllamaBackend()
    elif backend_type == "local":
        from .local import LocalBackend
        return LocalBackend()
    else:
        print(f"[Nova] Unknown backend '{backend_type}' — falling back to Ollama.")
        from .ollama import OllamaBackend
        return OllamaBackend()

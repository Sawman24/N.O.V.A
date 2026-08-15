import os
from typing import Generator
from .base import BaseBackend, get_config_val
from nova_logging import get_logger

logger = get_logger("backends.huggingface")


class HuggingFaceBackend(BaseBackend):
    """
    Runs a locally downloaded GGUF model using llama-cpp-python.

    Set HF_MODEL_FILE to the path of a .gguf file inside the models/ directory.
    GPU offloading is enabled by setting N_GPU_LAYERS env var (default: 0 = CPU only).
    """

    NAME = "huggingface"

    def __init__(self):
        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python is not installed. "
                "Run: pip install llama-cpp-python"
            )

        model_path = get_config_val("HF_MODEL_FILE", "")
        if not model_path or not os.path.exists(model_path):
            raise RuntimeError(
                f"HF_MODEL_FILE not set or file not found: '{model_path}'. "
                "Download a model first via the Settings → Hugging Face panel."
            )

        n_gpu_layers = get_config_val("N_GPU_LAYERS", 0)
        n_ctx = get_config_val("N_CTX", 4096)

        logger.info(
            f"Backend: HuggingFace — loading {model_path} "
            f"(n_gpu_layers={n_gpu_layers}, n_ctx={n_ctx})"
        )

        self._model_path = model_path
        self._llm = Llama(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=n_ctx,
            chat_format="chatml",
            verbose=False,
        )
        logger.info("Model loaded successfully.")

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _strip_tools(tools: list) -> list | None:
        """
        llama-cpp-python supports tool calling for some models but it depends
        on the chat_format. We pass tools through when provided; the model will
        simply ignore the field if it doesn't understand it.
        """
        return tools if tools else None

    # ── BaseBackend interface ────────────────────────────────────────────────

    def chat(self, messages: list, tools: list):
        """Non-streaming chat via llama_cpp.Llama.create_chat_completion."""
        kwargs = dict(
            messages=messages,
            temperature=get_config_val("TEMPERATURE", 0.7),
        )
        tool_list = self._strip_tools(tools)
        if tool_list:
            kwargs["tools"] = tool_list

        response = self._llm.create_chat_completion(**kwargs)

        # Return an object that matches the OpenAI message interface expected
        # by agent.py (.content and .tool_calls).
        return _LlamaChatMessage(response["choices"][0]["message"])

    def chat_stream(self, messages: list, tools: list) -> Generator:
        """Streaming chat — yields OpenAI-compatible chunk dicts wrapped in _LlamaChunk."""
        kwargs = dict(
            messages=messages,
            temperature=get_config_val("TEMPERATURE", 0.7),
            stream=True,
        )
        tool_list = self._strip_tools(tools)
        if tool_list:
            kwargs["tools"] = tool_list

        for chunk in self._llm.create_chat_completion(**kwargs):
            yield _LlamaChunk(chunk)

    def get_info(self) -> dict:
        return {
            "backend": self.NAME,
            "model": os.path.basename(self._model_path),
        }


# ── Shim objects ─────────────────────────────────────────────────────────────
# agent.py expects OpenAI SDK objects (.content, .tool_calls, .choices, etc.)
# These lightweight wrappers let llama-cpp's plain dicts quack like those objects.

class _LlamaChatMessage:
    """Wraps a llama-cpp message dict to look like an OpenAI ChatCompletionMessage."""

    def __init__(self, msg: dict):
        self.content = msg.get("content") or ""
        raw_tcs = msg.get("tool_calls") or []
        self.tool_calls = [_LlamaToolCall(tc) for tc in raw_tcs] or None


class _LlamaToolCall:
    """Wraps a llama-cpp tool_call dict."""

    def __init__(self, tc: dict):
        self.id = tc.get("id", "")
        self.type = tc.get("type", "function")
        self.function = _LlamaFunction(tc.get("function", {}))


class _LlamaFunction:
    def __init__(self, fn: dict):
        self.name = fn.get("name", "")
        self.arguments = fn.get("arguments", "{}")


class _LlamaChoice:
    def __init__(self, choice: dict):
        self.delta = _LlamaDelta(choice.get("delta", {}))


class _LlamaDelta:
    def __init__(self, delta: dict):
        self.content = delta.get("content")
        raw_tcs = delta.get("tool_calls") or []
        self.tool_calls = [_LlamaToolCallDelta(tc) for tc in raw_tcs] or None


class _LlamaToolCallDelta:
    def __init__(self, tc: dict):
        self.index = tc.get("index", 0)
        self.id = tc.get("id")
        self.function = _LlamaFunctionDelta(tc.get("function", {}))


class _LlamaFunctionDelta:
    def __init__(self, fn: dict):
        self.name = fn.get("name")
        self.arguments = fn.get("arguments")


class _LlamaChunk:
    """Wraps a llama-cpp streaming chunk to look like an OpenAI chunk."""

    def __init__(self, chunk: dict):
        self.choices = [_LlamaChoice(c) for c in chunk.get("choices", [])]

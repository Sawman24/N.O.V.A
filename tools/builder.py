import os
from openai import OpenAI


def build_tool(description: str, tool_name: str) -> str:
    """Uses the configured local model to generate and save a new Python tool to the tools directory."""
    backend_type = os.getenv("BACKEND", "ollama").lower().strip()
    if backend_type == "local":
        base_url = os.getenv("LOCAL_BASE_URL", "http://localhost:1234/v1")
        api_key = os.getenv("LOCAL_API_KEY", "local")
    else:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        api_key = os.getenv("LOCAL_API_KEY", "ollama")

    model = os.getenv("BUILDER_MODEL") or os.getenv("AGENT_MODEL", "qwen2.5:7b")

    client = OpenAI(base_url=base_url, api_key=api_key)

    prompt = (
        f"Write a Python function named '{tool_name}' that does the following: {description}.\n"
        "Requirements:\n"
        "- Single standalone function with type hints and a docstring\n"
        "- Import any needed standard libraries at the top\n"
        "- No classes, no markdown fences, no explanations — raw Python code only"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        code = response.choices[0].message.content.strip()

        # Strip markdown fences if the model included them
        for prefix in ("```python", "```"):
            if code.startswith(prefix):
                code = code[len(prefix):]
        if code.endswith("```"):
            code = code[:-3]

        filepath = f"tools/{tool_name}.py"
        with open(filepath, "w") as f:
            f.write(code.strip())

        return f"Tool '{tool_name}' created at {filepath}."
    except Exception as e:
        return f"Failed to build tool: {e}"

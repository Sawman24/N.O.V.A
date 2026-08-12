# Nova

A self-hosted, local-first agentic AI platform. Nova runs entirely on your hardware — no cloud APIs, no data leaving your machine.

## Features

- **Any local AI model** — plug in Ollama, LM Studio, Jan, vLLM, KoboldCPP, or any OpenAI-compatible local server
- **Pluggable tools** — drop a `.py` file in `tools/` and the agent can use it immediately, no restart needed
- **Personalized profiles** — `.txt` files in `profiles/` are injected into the system prompt at startup
- **Web UI** — chat interface + settings panel at `http://localhost:8000`
- **CLI mode** — run `python main.py` for a terminal interface
- **Email monitoring** (optional) — auto-triage and respond to emails via IMAP/SMTP

## Quick Start

### 1. Configure

```bash
cp .env.example .env
# Edit .env with your preferred backend and settings
```

### 2. Run with Docker (recommended)

```bash
docker-compose up -d
```

Open `http://localhost:8000`.

### 3. Run manually

```bash
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
# or for CLI:
python main.py
```

## Backends

| Backend | `BACKEND=` | Required env vars |
|---|---|---|
| Ollama | `ollama` (default) | `OLLAMA_BASE_URL`, `AGENT_MODEL` |
| LM Studio / Jan / vLLM / KoboldCPP / etc. | `local` | `LOCAL_BASE_URL`, `AGENT_MODEL` |

Set your backend in `.env`. Restart Nova to switch.

## Adding Tools

Drop a `.py` file in `tools/` with a function that has a docstring:

```python
def my_tool(param: str) -> str:
    """Does something useful. The docstring is shown to the AI as the tool description."""
    return f"Result: {param}"
```

Nova reloads tools on every request — no restart required.

## Profiles

Create a `.txt` file in `profiles/` with context about yourself. See `profiles/example.txt` for a template.
Profiles are injected into the system prompt at startup.

## Email (Optional)

Set `EMAIL_ADDRESS` and `EMAIL_APP_PASSWORD` in `.env`. Nova will check your inbox every 5 minutes and auto-triage. Leave these blank to disable email tools entirely.

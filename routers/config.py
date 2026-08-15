import os
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from dependencies import get_current_username
from nova_logging import get_logger

router = APIRouter(prefix="/api", tags=["config"])
logger = get_logger("routers.config")

CONFIG_PATH = "profiles/config.json"

EDITABLE_ENV = [
    "AGENT_MODEL",
    "BUILDER_MODEL",
    "BACKEND",
    "OLLAMA_BASE_URL",
    "LOCAL_BASE_URL",
    "LOCAL_API_KEY",
    # Hugging Face backend
    "HF_TOKEN",
    "HF_MODEL_FILE",
    "N_GPU_LAYERS",
    "N_CTX",
    "TEMPERATURE",
    "EMAIL_ADDRESS",
    "EMAIL_APP_PASSWORD",
    "IMAP_SERVER",
    "SMTP_SERVER",
    "HEADLESS_MODE",
]


class ConfigRequest(BaseModel):
    autonomous_mode: bool
    agent_model: str


class EnvRequest(BaseModel):
    vars: dict


def load_persistent_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_persistent_config(data: dict):
    config = load_persistent_config()
    config.update(data)
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write persistent config: {e}")


@router.get("/config")
async def get_config(username: str = Depends(get_current_username)):
    config = load_persistent_config()
    return {
        "autonomous_mode": not config.get("require_human_confirmation", False),
        "agent_model": config.get("AGENT_MODEL", os.getenv("AGENT_MODEL", "qwen2.5:7b")),
        "backend": config.get("BACKEND", os.getenv("BACKEND", "ollama")),
    }


@router.post("/config")
async def save_config(req: ConfigRequest, username: str = Depends(get_current_username)):
    save_persistent_config({
        "require_human_confirmation": not req.autonomous_mode,
        "AGENT_MODEL": req.agent_model,
    })
    os.environ["AGENT_MODEL"] = req.agent_model
    return {"status": "success"}


@router.get("/env")
async def get_env(username: str = Depends(get_current_username)):
    """Return current values of all editable env vars, prioritizing persistent config."""
    config = load_persistent_config()
    return {k: config.get(k, os.getenv(k, "")) for k in EDITABLE_ENV}


@router.post("/env")
async def save_env(req: EnvRequest, username: str = Depends(get_current_username)):
    """Update env vars live, save them to profiles/config.json, and try to persist to .env."""
    # 1. Update in-memory os.environ
    for key, value in req.vars.items():
        if key in EDITABLE_ENV:
            os.environ[key] = value

    # 2. Save to persistent volume profiles/config.json
    save_persistent_config({k: v for k, v in req.vars.items() if k in EDITABLE_ENV})

    # 3. Try to save to local .env (for non-docker / manual setups)
    try:
        existing = {}
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        existing[k] = v

        for k in EDITABLE_ENV:
            existing[k] = os.getenv(k, "")

        lines = [f"{k}={v}" for k, v in existing.items()]
        with open(".env", "w") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        logger.error(f"Could not write .env: {e}")

    return {"status": "success"}


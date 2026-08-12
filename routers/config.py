import os
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from dependencies import get_current_username

router = APIRouter(prefix="/api", tags=["config"])

EDITABLE_ENV = [
    "AGENT_MODEL",
    "BUILDER_MODEL",
    "BACKEND",
    "OLLAMA_BASE_URL",
    "LOCAL_BASE_URL",
    "LOCAL_API_KEY",
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


@router.get("/config")
async def get_config(username: str = Depends(get_current_username)):
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except Exception:
        config = {}
    return {
        "autonomous_mode": not config.get("require_human_confirmation", False),
        "agent_model": os.getenv("AGENT_MODEL", "qwen2.5:7b"),
        "backend": os.getenv("BACKEND", "ollama"),
    }


@router.post("/config")
async def save_config(req: ConfigRequest, username: str = Depends(get_current_username)):
    with open("config.json", "w") as f:
        json.dump({"require_human_confirmation": not req.autonomous_mode}, f)
    os.environ["AGENT_MODEL"] = req.agent_model
    return {"status": "success"}


@router.get("/env")
async def get_env(username: str = Depends(get_current_username)):
    """Return current values of all editable env vars."""
    return {k: os.getenv(k, "") for k in EDITABLE_ENV}


@router.post("/env")
async def save_env(req: EnvRequest, username: str = Depends(get_current_username)):
    """Update env vars live and try to persist them to .env."""
    for key, value in req.vars.items():
        if key in EDITABLE_ENV:
            os.environ[key] = value

    try:
        # Read existing .env to preserve non-editable vars (e.g. WEB_USERNAME, WEB_PASSWORD)
        existing = {}
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        existing[k] = v

        # Update editable vars with current env values
        for k in EDITABLE_ENV:
            existing[k] = os.getenv(k, "")

        lines = [f"{k}={v}" for k, v in existing.items()]
        with open(".env", "w") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"[Nova] Could not write .env: {e}")

    return {"status": "success"}


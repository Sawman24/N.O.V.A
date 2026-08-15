import os
from fastapi import APIRouter, Response
from pydantic import BaseModel
from dependencies import (
    is_default_password,
    create_session_token,
    SESSION_COOKIE_NAME,
    SESSION_EXPIRY_SECONDS,
)
from nova_logging import get_logger

router = APIRouter(prefix="/api", tags=["setup"])
logger = get_logger("routers.setup")


class SetupRequest(BaseModel):
    username: str
    password: str


@router.get("/setup/status")
async def setup_status():
    """Check if first-time setup is needed (default password still in use)."""
    return {"needs_setup": is_default_password()}


@router.post("/setup")
async def setup(req: SetupRequest, response: Response):
    """Set initial credentials during first-time setup."""
    if not is_default_password():
        return {"status": "error", "message": "Setup already completed. Change credentials via the Environment tab."}

    if len(req.password) < 8:
        return {"status": "error", "message": "Password must be at least 8 characters."}

    if not req.username.strip():
        return {"status": "error", "message": "Username cannot be empty."}

    # Update env vars
    os.environ["WEB_USERNAME"] = req.username.strip()
    os.environ["WEB_PASSWORD"] = req.password

    # Persist to .env
    try:
        existing = {}
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        existing[k] = v

        existing["WEB_USERNAME"] = req.username.strip()
        existing["WEB_PASSWORD"] = req.password

        lines = [f"{k}={v}" for k, v in existing.items()]
        with open(".env", "w") as f:
            f.write("\n".join(lines) + "\n")

        logger.info(f"Setup completed — credentials updated for user '{req.username.strip()}'.")
    except Exception as e:
        logger.error(f"Could not write .env during setup: {e}")
        return {"status": "error", "message": f"Credentials set in memory but could not persist to .env: {e}"}

    # Issue session cookie so they don't need to log in again immediately
    token = create_session_token(req.username.strip())
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_EXPIRY_SECONDS,
        httponly=True,
        samesite="strict",
    )

    return {"status": "success"}

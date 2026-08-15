import os
import hmac
import hashlib
import time
import secrets
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv
from agent import NovaAgent
from nova_logging import get_logger

load_dotenv()

logger = get_logger("dependencies")

from backends.base import get_config_val

WEB_USERNAME = get_config_val("WEB_USERNAME", "admin")
WEB_PASSWORD = get_config_val("WEB_PASSWORD", "changeme")
security = HTTPBasic(auto_error=False)

# Session token management
SESSION_SECRET = secrets.token_hex(32)
SESSION_COOKIE_NAME = "nova_session"
SESSION_EXPIRY_SECONDS = 86400  # 24 hours

agent = NovaAgent()


def is_default_password() -> bool:
    """Check if the password is still the insecure default."""
    return os.getenv("WEB_PASSWORD", "changeme") == "changeme"


def get_agent() -> NovaAgent:
    return agent


def create_session_token(username: str) -> str:
    """Create a signed session token with embedded expiry."""
    expires = int(time.time()) + SESSION_EXPIRY_SECONDS
    payload = f"{username}:{expires}"
    signature = hmac.new(
        SESSION_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_session_token(token: str) -> str | None:
    """Verify a session token and return the username, or None if invalid."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        username, expires_str, signature = parts
        payload = f"{username}:{expires_str}"
        expected = hmac.new(
            SESSION_SECRET.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        if int(expires_str) < int(time.time()):
            return None
        return username
    except Exception:
        return None


async def get_current_username(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> str:
    """Authenticate via session cookie first, then fall back to HTTP Basic Auth."""
    # 1. Try session cookie
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        username = verify_session_token(token)
        if username:
            return username

    # 2. Fall back to Basic Auth
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    current_user = os.getenv("WEB_USERNAME", "admin")
    current_pass = os.getenv("WEB_PASSWORD", "changeme")

    ok_user = secrets.compare_digest(credentials.username, current_user)
    ok_pass = secrets.compare_digest(credentials.password, current_pass)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

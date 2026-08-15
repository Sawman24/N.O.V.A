from fastapi import APIRouter, Depends, Response, HTTPException
from fastapi.security import HTTPBasicCredentials
from dependencies import (
    security,
    create_session_token,
    get_current_username,
    SESSION_COOKIE_NAME,
    SESSION_EXPIRY_SECONDS,
)
from nova_logging import get_logger
import os
import secrets

router = APIRouter(prefix="/api", tags=["auth"])
logger = get_logger("routers.auth")


@router.post("/login")
async def login(
    response: Response,
    credentials: HTTPBasicCredentials = Depends(security),
):
    """Authenticate and receive a session cookie."""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Credentials required",
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

    token = create_session_token(credentials.username)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_EXPIRY_SECONDS,
        httponly=True,
        samesite="strict",
    )
    return {"status": "success", "username": credentials.username}


@router.post("/logout")
async def logout(
    response: Response,
    username: str = Depends(get_current_username),
):
    """Clear the session cookie."""
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"status": "logged_out"}

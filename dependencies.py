import os
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv
from agent import NovaAgent

load_dotenv()

WEB_USERNAME = os.getenv("WEB_USERNAME", "admin")
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "changeme")
security = HTTPBasic()

agent = NovaAgent()


def get_agent() -> NovaAgent:
    return agent


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    ok_user = secrets.compare_digest(credentials.username, WEB_USERNAME)
    ok_pass = secrets.compare_digest(credentials.password, WEB_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

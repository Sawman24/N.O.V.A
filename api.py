import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from nova_logging import get_logger

load_dotenv()

logger = get_logger("api")

from dependencies import agent, is_default_password
from routers.chat import router as chat_router
from routers.config import router as config_router
from routers.models import router as models_router
from routers.profiles import router as profiles_router
from routers.ws_bridge import router as ws_router
from routers.setup import router as setup_router
from routers.auth import router as auth_router


# --- Background email monitor ---
async def email_monitor_task():
    if not os.getenv("EMAIL_ADDRESS"):
        return
    logger.info("Email monitor started.")
    while True:
        try:
            await asyncio.sleep(300)
            agent.registry.load_tools()
            if "check_inbox" in agent.registry.tools:
                emails = agent.registry.tools["check_inbox"]()
                if emails and "No" not in emails and "Error" not in emails:
                    prompt = (
                        f"SYSTEM: New emails:\n\n{emails}\n\n"
                        "Review and auto-respond if appropriate, or summarize."
                    )
                    agent.chat(prompt, session_id="email_monitor")
        except Exception as e:
            logger.error(f"Email monitor error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(email_monitor_task())
    yield


app = FastAPI(lifespan=lifespan)


# --- Setup-required middleware ---
SETUP_ALLOWED_PATHS = {"/api/health", "/api/setup", "/api/setup/status"}


@app.middleware("http")
async def require_setup_middleware(request: Request, call_next):
    """Block all API routes except health and setup when default password is active."""
    path = request.url.path
    if is_default_password() and path.startswith("/api") and path not in SETUP_ALLOWED_PATHS:
        return JSONResponse(
            status_code=403,
            content={"detail": "Setup required. Please set a secure password before using Nova."},
        )
    return await call_next(request)


# --- Include Routers ---
app.include_router(setup_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(config_router)
app.include_router(models_router)
app.include_router(profiles_router)
app.include_router(ws_router)


# --- Public / Unauthenticated Endpoints ---
@app.get("/api/health")
async def health():
    """Health check — used by Docker and load balancers."""
    return {"status": "ok", "backend": os.getenv("BACKEND", "ollama")}


# --- Static files ---
os.makedirs("web", exist_ok=True)
app.mount("/", StaticFiles(directory="web", html=True), name="web")


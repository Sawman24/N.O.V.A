import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from dependencies import agent
from routers.chat import router as chat_router
from routers.config import router as config_router
from routers.models import router as models_router
from routers.profiles import router as profiles_router


# --- Background email monitor ---
async def email_monitor_task():
    if not os.getenv("EMAIL_ADDRESS"):
        return
    print("[Nova] Email monitor started...")
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
            print(f"[Nova] Email monitor error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(email_monitor_task())
    yield


app = FastAPI(lifespan=lifespan)

# --- Include Routers ---
app.include_router(chat_router)
app.include_router(config_router)
app.include_router(models_router)
app.include_router(profiles_router)


# --- Public / Unauthenticated Endpoints ---
@app.get("/api/health")
async def health():
    """Health check — used by Docker and load balancers."""
    return {"status": "ok", "backend": os.getenv("BACKEND", "ollama")}


# --- Static files ---
os.makedirs("web", exist_ok=True)
app.mount("/", StaticFiles(directory="web", html=True), name="web")

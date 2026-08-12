import os
import json
import asyncio
import urllib.request
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import secrets
from dotenv import load_dotenv

load_dotenv()
from agent import NovaAgent

# --- Auth ---
WEB_USERNAME = os.getenv("WEB_USERNAME", "admin")
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "changeme")
security = HTTPBasic()

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, WEB_USERNAME)
    ok_pass = secrets.compare_digest(credentials.password, WEB_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

agent = NovaAgent()

# --- Background email monitor (only runs if EMAIL_ADDRESS is set) ---
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
                    agent.chat(prompt)
        except Exception as e:
            print(f"[Nova] Email monitor error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(email_monitor_task())
    yield

app = FastAPI(lifespan=lifespan)

# --- Helpers ---
def _ollama_base() -> str:
    """Return the Ollama base URL without the /v1 suffix."""
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").replace("/v1", "")

# --- Request models ---
class ChatRequest(BaseModel):
    message: str

class ProfileRequest(BaseModel):
    name: str
    content: str

class ConfigRequest(BaseModel):
    autonomous_mode: bool
    agent_model: str

class ModelRequest(BaseModel):
    model_name: str

# --- Endpoints ---

@app.get("/api/health")
async def health():
    """Health check — used by Docker and load balancers."""
    return {"status": "ok", "backend": os.getenv("BACKEND", "ollama")}

@app.get("/api/backend")
async def get_backend_info(username: str = Depends(get_current_username)):
    return agent.backend.get_info()

@app.post("/api/chat")
async def chat(req: ChatRequest, username: str = Depends(get_current_username)):
    try:
        response = agent.chat(req.message)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
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

@app.post("/api/config")
async def save_config(req: ConfigRequest, username: str = Depends(get_current_username)):
    with open("config.json", "w") as f:
        json.dump({"require_human_confirmation": not req.autonomous_mode}, f)
    # Update the running process so the model switches immediately — no restart needed
    os.environ["AGENT_MODEL"] = req.agent_model
    return {"status": "success"}

@app.get("/api/profiles")
async def list_profiles(username: str = Depends(get_current_username)):
    profiles = []
    if os.path.exists("profiles"):
        for filename in sorted(os.listdir("profiles")):
            if filename.endswith(".txt"):
                with open(os.path.join("profiles", filename), "r") as f:
                    profiles.append({
                        "name": filename.replace(".txt", ""),
                        "content": f.read()
                    })
    return profiles

@app.post("/api/profiles")
async def save_profile(req: ProfileRequest, username: str = Depends(get_current_username)):
    os.makedirs("profiles", exist_ok=True)
    filename = f"{req.name.strip().replace(' ', '_').lower()}.txt"
    with open(os.path.join("profiles", filename), "w") as f:
        f.write(req.content)
    return {"status": "success"}

@app.get("/api/models")
async def list_models(username: str = Depends(get_current_username)):
    """List locally installed Ollama models. Returns empty list for non-Ollama backends."""
    if os.getenv("BACKEND", "ollama") != "ollama":
        return {"models": []}
    try:
        url = f"{_ollama_base()}/api/tags"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            return {
                "models": [
                    {
                        "name": m["name"],
                        "size_gb": round(m.get("size", 0) / 1e9, 1)
                    }
                    for m in data.get("models", [])
                ]
            }
    except Exception as e:
        return {"models": [], "error": str(e)}

@app.post("/api/models/download")
async def download_model(req: ModelRequest, username: str = Depends(get_current_username)):
    """
    Stream model download progress from Ollama as Server-Sent Events.
    The client reads the stream and updates a progress bar in real time.
    Only available when BACKEND=ollama.
    """
    if os.getenv("BACKEND", "ollama") != "ollama":
        raise HTTPException(status_code=400, detail="Model download is only available for the Ollama backend.")

    def stream_pull():
        url = f"{_ollama_base()}/api/pull"
        data = json.dumps({"name": req.model_name, "stream": True}).encode()
        http_req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(http_req, timeout=900) as response:
                while True:
                    line = response.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8").strip()
                    if decoded:
                        yield f"data: {decoded}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        stream_pull(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disables nginx buffering for SSE
        }
    )

# --- Static files ---
os.makedirs("web", exist_ok=True)
app.mount("/", StaticFiles(directory="web", html=True), name="web")

import os
import json
import urllib.request
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dependencies import get_current_username

router = APIRouter(prefix="/api", tags=["models"])


def _ollama_base() -> str:
    """Return the Ollama base URL without the /v1 suffix."""
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").replace("/v1", "")


class ModelRequest(BaseModel):
    model_name: str


@router.get("/models")
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


@router.post("/models/download")
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
            "X-Accel-Buffering": "no",
        }
    )

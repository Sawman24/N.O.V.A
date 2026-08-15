import os
import json
import urllib.request
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dependencies import get_current_username

router = APIRouter(prefix="/api", tags=["models"])

# Ensure the models directory always exists
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)


def _ollama_base() -> str:
    """Return the Ollama base URL without the /v1 suffix."""
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").replace("/v1", "")


class ModelRequest(BaseModel):
    model_name: str


class HFDownloadRequest(BaseModel):
    repo_id: str
    filename: str


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


# ── Hugging Face endpoints ────────────────────────────────────────────────────

@router.get("/hf/models")
async def list_hf_models(username: str = Depends(get_current_username)):
    """Return all .gguf files that have already been downloaded to models/."""
    files = sorted(
        [
            {"filename": f.name, "size_gb": round(f.stat().st_size / 1e9, 2)}
            for f in MODELS_DIR.glob("*.gguf")
        ],
        key=lambda x: x["filename"],
    )
    return {"models": files}


@router.get("/hf/files")
async def list_hf_files(repo_id: str, username: str = Depends(get_current_username)):
    """
    Fetch the list of GGUF files available in a Hugging Face repo.
    Uses the HF Hub API — no authentication required for public models.
    Pass HF_TOKEN in env for gated/private repos.
    """
    try:
        from huggingface_hub import list_repo_files, HfApi
        token = os.getenv("HF_TOKEN") or None
        all_files = list(list_repo_files(repo_id, token=token))
        gguf_files = [f for f in all_files if f.lower().endswith(".gguf")]
        if not gguf_files:
            return {"files": [], "warning": "No GGUF files found in this repository."}
        return {"files": gguf_files, "repo_id": repo_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/hf/download")
async def download_hf_model(req: HFDownloadRequest, username: str = Depends(get_current_username)):
    """
    Stream-download a specific GGUF file from Hugging Face to models/.
    Progress is emitted as Server-Sent Events with bytes_downloaded, total_bytes, and pct fields.
    """
    dest_path = MODELS_DIR / Path(req.filename).name
    token = os.getenv("HF_TOKEN") or None

    def stream_download():
        try:
            from huggingface_hub import hf_hub_url
            import urllib.request

            url = hf_hub_url(req.repo_id, req.filename)
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            hf_req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(hf_req, timeout=1800) as response:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 1024 * 1024  # 1 MB chunks

                # Open destination file
                with open(dest_path, "wb") as out:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out.write(chunk)
                        downloaded += len(chunk)
                        pct = round((downloaded / total) * 100, 1) if total else 0
                        payload = json.dumps({
                            "bytes_downloaded": downloaded,
                            "total_bytes": total,
                            "pct": pct,
                            "filename": Path(req.filename).name,
                        })
                        yield f"data: {payload}\n\n"

            yield f"data: {json.dumps({'done': True, 'path': str(dest_path), 'filename': dest_path.name})}\n\n"

        except Exception as e:
            # Clean up partial download
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_download(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

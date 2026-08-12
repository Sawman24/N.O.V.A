import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from dependencies import get_current_username, get_agent
from agent import NovaAgent

router = APIRouter(prefix="/api", tags=["profiles"])


class ProfileRequest(BaseModel):
    name: str
    content: str


@router.get("/profiles")
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


@router.post("/profiles")
async def save_profile(
    req: ProfileRequest,
    username: str = Depends(get_current_username),
    agent: NovaAgent = Depends(get_agent),
):
    os.makedirs("profiles", exist_ok=True)
    filename = f"{req.name.strip().replace(' ', '_').lower()}.txt"
    with open(os.path.join("profiles", filename), "w") as f:
        f.write(req.content)
    agent.reload_profiles()
    return {"status": "success"}

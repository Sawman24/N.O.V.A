from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from dependencies import get_current_username, get_agent
from agent import NovaAgent

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


@router.get("/backend")
async def get_backend_info(
    username: str = Depends(get_current_username),
    agent: NovaAgent = Depends(get_agent),
):
    return agent.backend.get_info()


@router.post("/chat")
async def chat(
    req: ChatRequest,
    username: str = Depends(get_current_username),
    agent: NovaAgent = Depends(get_agent),
):
    try:
        response = agent.chat(req.message, session_id=req.session_id)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.llm import chat

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    messages: list[dict]


class ChatResponse(BaseModel):
    content: str
    model: str


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        content = await chat(req.messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return ChatResponse(content=content, model="gpt-4o-mini")

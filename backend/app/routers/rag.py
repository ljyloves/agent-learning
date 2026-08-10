from fastapi import APIRouter
from pydantic import BaseModel

from app.services.rag import rag_query

router = APIRouter(prefix="/rag", tags=["rag"])


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


class SourceItem(BaseModel):
    source: str
    score: float
    text: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    result = await rag_query(req.question, top_k=req.top_k)
    return QueryResponse(answer=result["answer"], sources=result["sources"])

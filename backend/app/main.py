from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.qdrant import init_collections
from app.modules import paper_agent
from app.modules.paper_agent.graph.checkpoint import create_paper_graph_runtime
from app.routers import health, chat, documents, rag

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_collections()
    async with create_paper_graph_runtime() as runtime:
        app.state.paper_agent_graph = runtime.graph
        app.state.paper_agent_teacher_review_graph = runtime.teacher_review_graph
        app.state.paper_agent_conversation_graph = runtime.conversation_graph
        app.state.paper_agent_checkpointer = runtime.checkpointer
        yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(paper_agent.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(rag.router, prefix="/api")

@app.get("/")
async def root():
    return {"service": settings.app_name, "version": "0.1.0"}

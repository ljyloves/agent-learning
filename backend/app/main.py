from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.qdrant import init_collections
from app.modules import paper_agent
from app.routers import health, chat, documents, rag

app = FastAPI(title=settings.app_name, version="0.1.0")

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


@app.on_event("startup")
async def startup():
    init_collections()


@app.get("/")
async def root():
    return {"service": settings.app_name, "version": "0.1.0"}

"""High school biology paper generation module."""

from app.modules.paper_agent.router import router
from app.modules.paper_agent.conversation_router import router as conversation_router

router.include_router(conversation_router)

__all__ = ["router"]

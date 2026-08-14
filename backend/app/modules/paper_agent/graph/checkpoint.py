"""PostgreSQL-backed runtime for the paper-generation graph."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph.state import CompiledStateGraph
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import settings
from app.modules.paper_agent.graph.workflow import (
    build_paper_agent_graph,
    build_teacher_review_graph,
)
from app.modules.paper_agent.graph.conversation_workflow import (
    build_conversation_agent_graph,
)
from app.modules.paper_agent.services.conversation_graph import (
    build_conversation_workflow_handlers,
)


CHECKPOINT_ALLOWED_MSGPACK_MODULES = [
    ("app.modules.paper_agent.graph.state", "PaperGraphDecision"),
    ("app.modules.paper_agent.graph.state", "PaperGraphReportLevel"),
    (
        "app.modules.paper_agent.schemas.conversation_graph",
        "ConversationGraphStatus",
    ),
    ("app.modules.paper_agent.schemas.paper_job", "PaperJobStatus"),
]


@dataclass(frozen=True, slots=True)
class PaperGraphRuntime:
    graph: CompiledStateGraph
    teacher_review_graph: CompiledStateGraph
    conversation_graph: CompiledStateGraph
    checkpointer: AsyncPostgresSaver
    pool: AsyncConnectionPool


@asynccontextmanager
async def create_paper_graph_runtime() -> AsyncIterator[PaperGraphRuntime]:
    """Own the pool, schema setup, saver, and compiled graph as one resource."""

    pool = AsyncConnectionPool(
        conninfo=settings.checkpointer_database_url,
        min_size=settings.paper_agent_checkpoint_pool_min_size,
        max_size=settings.paper_agent_checkpoint_pool_max_size,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=False,
        name="paper-agent-checkpoints",
    )
    await pool.open(wait=True, timeout=30.0)
    try:
        checkpointer = AsyncPostgresSaver(
            pool,
            serde=JsonPlusSerializer(
                allowed_msgpack_modules=CHECKPOINT_ALLOWED_MSGPACK_MODULES,
            ),
        )
        await checkpointer.setup()
        teacher_review_graph = build_teacher_review_graph(
            checkpointer=checkpointer
        )
        yield PaperGraphRuntime(
            graph=build_paper_agent_graph(checkpointer=checkpointer),
            teacher_review_graph=teacher_review_graph,
            conversation_graph=build_conversation_agent_graph(
                build_conversation_workflow_handlers(teacher_review_graph),
                checkpointer=checkpointer,
            ),
            checkpointer=checkpointer,
            pool=pool,
        )
    finally:
        await pool.close()

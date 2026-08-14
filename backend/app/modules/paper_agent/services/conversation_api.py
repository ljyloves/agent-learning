"""Application services for the conversational Agent REST API."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationMessageModel, ConversationModel
from app.modules.paper_agent.schemas.conversation import (
    ConversationCreate,
    ConversationHistoryResponse,
    ConversationMessage,
    ConversationMessageCreate,
    ConversationPlanResponse,
    ConversationPlanUpdate,
    ConversationRead,
    MessageRole,
)
from app.modules.paper_agent.schemas.conversation_graph import (
    ConversationGraphCommand,
    ConversationGraphStatusResponse,
)
from app.modules.paper_agent.services.conversation_graph import (
    ConversationGraphBusyError,
    get_conversation_graph_status,
    resume_conversation_turn,
    start_conversation_plan_turn,
    start_conversation_turn,
)
from app.modules.paper_agent.services.conversation_store import (
    ConversationNotFoundError,
    append_message,
    load_plan,
    save_plan,
)


async def create_conversation(
    session: AsyncSession,
    payload: ConversationCreate,
) -> ConversationRead:
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    existing = await session.get(ConversationModel, conversation_id)
    if existing is not None:
        if existing.title != payload.title:
            raise ValueError("conversation_id already exists with a different title")
        return ConversationRead.model_validate(existing)
    conversation = ConversationModel(
        conversation_id=conversation_id,
        title=payload.title,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return ConversationRead.model_validate(conversation)


async def get_conversation(
    session: AsyncSession,
    conversation_id: str,
) -> ConversationRead:
    conversation = await session.get(ConversationModel, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(conversation_id)
    return ConversationRead.model_validate(conversation)


async def get_conversation_history(
    session: AsyncSession,
    conversation_id: str,
) -> ConversationHistoryResponse:
    conversation = await get_conversation(session, conversation_id)
    models = list(
        await session.scalars(
            select(ConversationMessageModel)
            .where(ConversationMessageModel.conversation_id == conversation_id)
            .order_by(ConversationMessageModel.sequence_no)
        )
    )
    return ConversationHistoryResponse(
        conversation=conversation,
        messages=[ConversationMessage.model_validate(model) for model in models],
    )


async def get_conversation_plan(
    session: AsyncSession,
    conversation_id: str,
) -> ConversationPlanResponse:
    conversation = await get_conversation(session, conversation_id)
    plan = await load_plan(session, conversation_id)
    return ConversationPlanResponse(
        conversation_id=conversation_id,
        active_plan_version=conversation.active_plan_version,
        plan=plan,
    )


async def submit_conversation_message(
    session: AsyncSession,
    graph,
    conversation_id: str,
    payload: ConversationMessageCreate,
) -> ConversationGraphStatusResponse:
    existing = await get_conversation_graph_status(graph, conversation_id)
    if existing is not None and existing.state.message_id != payload.message_id:
        if existing.interrupted:
            raise ConversationGraphBusyError(existing.state.pending_action_id)
    await append_message(
        session,
        message_id=payload.message_id,
        conversation_id=conversation_id,
        role=MessageRole.TEACHER,
        content=payload.content,
    )
    await session.commit()
    if existing is not None and existing.state.message_id == payload.message_id:
        return existing
    return await start_conversation_turn(
        graph,
        conversation_id,
        payload.message_id,
    )


async def get_conversation_status(
    session: AsyncSession,
    graph,
    conversation_id: str,
) -> ConversationGraphStatusResponse | None:
    await get_conversation(session, conversation_id)
    return await get_conversation_graph_status(graph, conversation_id)


async def update_conversation_plan(
    session: AsyncSession,
    graph,
    conversation_id: str,
    payload: ConversationPlanUpdate,
) -> ConversationGraphStatusResponse:
    existing = await get_conversation_graph_status(graph, conversation_id)
    if existing is not None and existing.state.message_id != payload.message_id:
        if existing.interrupted:
            raise ConversationGraphBusyError(existing.state.pending_action_id)
    await append_message(
        session,
        message_id=payload.message_id,
        conversation_id=conversation_id,
        role=MessageRole.TEACHER,
        content="通过结构化表单更新组卷方案。",
        attributes={"source": "structured_form"},
    )
    version = await save_plan(
        session,
        conversation_id=conversation_id,
        source_message_id=payload.message_id,
        plan=payload.plan,
    )
    await session.commit()
    if existing is not None and existing.state.message_id == payload.message_id:
        return existing
    return await start_conversation_plan_turn(
        graph,
        conversation_id,
        payload.message_id,
        version,
    )


async def command_conversation(
    session: AsyncSession,
    graph,
    conversation_id: str,
    command: ConversationGraphCommand,
) -> ConversationGraphStatusResponse:
    await get_conversation(session, conversation_id)
    return await resume_conversation_turn(graph, conversation_id, command)

"""Transactional persistence helpers for conversational paper generation."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ConversationMessageModel,
    ConversationModel,
    PaperPlanVersionModel,
    PendingActionModel,
)
from app.modules.paper_agent.schemas.conversation import (
    MessageRole,
    PaperPlan,
    PendingActionStatus,
    PendingActionType,
)


class ConversationNotFoundError(LookupError):
    pass


class ConversationMessageNotFoundError(LookupError):
    pass


class PaperPlanNotFoundError(LookupError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def append_message(
    session: AsyncSession,
    *,
    message_id: str,
    conversation_id: str,
    role: MessageRole,
    content: str,
    attributes: dict | None = None,
) -> ConversationMessageModel:
    existing = await session.get(ConversationMessageModel, message_id)
    if existing is not None:
        if existing.conversation_id != conversation_id:
            raise ValueError("message_id belongs to another conversation")
        if (
            existing.role != role.value
            or existing.content != content
            or existing.attributes != (attributes or {})
        ):
            raise ValueError("message_id was reused with different content")
        return existing
    conversation = await session.scalar(
        select(ConversationModel)
        .where(ConversationModel.conversation_id == conversation_id)
        .with_for_update()
    )
    if conversation is None:
        raise ConversationNotFoundError(conversation_id)
    sequence_no = int(
        await session.scalar(
            select(func.coalesce(func.max(ConversationMessageModel.sequence_no), 0))
            .where(ConversationMessageModel.conversation_id == conversation_id)
        )
        or 0
    ) + 1
    message = ConversationMessageModel(
        message_id=message_id,
        conversation_id=conversation_id,
        sequence_no=sequence_no,
        role=role.value,
        content=content,
        attributes=attributes or {},
    )
    session.add(message)
    conversation.updated_at = utc_now()
    await session.flush()
    return message


async def load_message(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
) -> ConversationMessageModel:
    message = await session.get(ConversationMessageModel, message_id)
    if message is None or message.conversation_id != conversation_id:
        raise ConversationMessageNotFoundError(message_id)
    return message


async def load_plan(
    session: AsyncSession,
    conversation_id: str,
    version: int | None = None,
) -> PaperPlan | None:
    if version is None:
        conversation = await session.get(ConversationModel, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        version = conversation.active_plan_version
    if version == 0:
        return None
    model = await session.scalar(
        select(PaperPlanVersionModel).where(
            PaperPlanVersionModel.conversation_id == conversation_id,
            PaperPlanVersionModel.version == version,
        )
    )
    if model is None:
        raise PaperPlanNotFoundError(f"{conversation_id}:{version}")
    return PaperPlan.model_validate(model.plan)


async def save_plan(
    session: AsyncSession,
    *,
    conversation_id: str,
    source_message_id: str,
    plan: PaperPlan,
) -> int:
    existing = await session.scalar(
        select(PaperPlanVersionModel).where(
            PaperPlanVersionModel.conversation_id == conversation_id,
            PaperPlanVersionModel.source_message_id == source_message_id,
        )
    )
    if existing is not None:
        if PaperPlan.model_validate(existing.plan) != plan:
            raise ValueError("source message already produced a different plan")
        return existing.version
    conversation = await session.scalar(
        select(ConversationModel)
        .where(ConversationModel.conversation_id == conversation_id)
        .with_for_update()
    )
    if conversation is None:
        raise ConversationNotFoundError(conversation_id)
    version = conversation.active_plan_version + 1
    session.add(
        PaperPlanVersionModel(
            conversation_id=conversation_id,
            version=version,
            source_message_id=source_message_id,
            plan=plan.model_dump(mode="json"),
        )
    )
    conversation.active_plan_version = version
    conversation.updated_at = utc_now()
    await session.flush()
    return version


async def create_pending_action(
    session: AsyncSession,
    *,
    action_id: str,
    conversation_id: str,
    action_type: PendingActionType,
    source_message_id: str | None,
    plan_version: int | None,
    request_payload: dict,
) -> PendingActionModel:
    action = PendingActionModel(
        action_id=action_id,
        conversation_id=conversation_id,
        action_type=action_type.value,
        status=PendingActionStatus.PENDING.value,
        source_message_id=source_message_id,
        plan_version=plan_version,
        request_payload=request_payload,
    )
    session.add(action)
    await session.flush()
    return action

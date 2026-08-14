"""REST endpoints for conversational paper generation."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.paper_agent.schemas.conversation import (
    ConversationCreate,
    ConversationHistoryResponse,
    ConversationMessageCreate,
    ConversationPlanResponse,
    ConversationPlanUpdate,
    ConversationRead,
)
from app.modules.paper_agent.schemas.conversation_graph import (
    ConversationGraphCommand,
    ConversationGraphStatusResponse,
)
from app.modules.paper_agent.services.conversation_api import (
    command_conversation,
    create_conversation,
    get_conversation,
    get_conversation_history,
    get_conversation_plan,
    get_conversation_status,
    submit_conversation_message,
    update_conversation_plan,
)
from app.modules.paper_agent.services.conversation_graph import (
    ConversationGraphBusyError,
    ConversationGraphClosedError,
    ConversationGraphNotFoundError,
    ConversationGraphNotInterruptedError,
)
from app.modules.paper_agent.services.conversation_store import (
    ConversationNotFoundError,
)


router = APIRouter(prefix="/conversations")
ConversationId = Annotated[
    str,
    Path(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]


def get_conversation_graph(request: Request) -> Any:
    graph = getattr(request.app.state, "paper_agent_conversation_graph", None)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONVERSATION_GRAPH_UNAVAILABLE",
                "message": "对话式组卷服务尚未就绪。",
                "retryable": True,
            },
        )
    return graph


def api_error(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": retryable},
    )


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation_endpoint(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    try:
        return await create_conversation(db, payload)
    except (ValueError, IntegrityError) as exc:
        await db.rollback()
        raise api_error(
            status.HTTP_409_CONFLICT,
            "CONVERSATION_CONFLICT",
            "会话编号已被其他会话使用。",
        ) from exc


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation_endpoint(
    conversation_id: ConversationId,
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    try:
        return await get_conversation(db, conversation_id)
    except ConversationNotFoundError as exc:
        raise api_error(404, "CONVERSATION_NOT_FOUND", "未找到该组卷会话。") from exc


@router.get(
    "/{conversation_id}/history",
    response_model=ConversationHistoryResponse,
)
async def get_history_endpoint(
    conversation_id: ConversationId,
    db: AsyncSession = Depends(get_db),
) -> ConversationHistoryResponse:
    try:
        return await get_conversation_history(db, conversation_id)
    except ConversationNotFoundError as exc:
        raise api_error(404, "CONVERSATION_NOT_FOUND", "未找到该组卷会话。") from exc


@router.get(
    "/{conversation_id}/plan",
    response_model=ConversationPlanResponse,
)
async def get_plan_endpoint(
    conversation_id: ConversationId,
    db: AsyncSession = Depends(get_db),
) -> ConversationPlanResponse:
    try:
        return await get_conversation_plan(db, conversation_id)
    except ConversationNotFoundError as exc:
        raise api_error(404, "CONVERSATION_NOT_FOUND", "未找到该组卷会话。") from exc


@router.put(
    "/{conversation_id}/plan",
    response_model=ConversationGraphStatusResponse,
)
async def update_plan_endpoint(
    conversation_id: ConversationId,
    payload: ConversationPlanUpdate,
    db: AsyncSession = Depends(get_db),
    graph: Any = Depends(get_conversation_graph),
) -> ConversationGraphStatusResponse:
    try:
        return await update_conversation_plan(
            db,
            graph,
            conversation_id,
            payload,
        )
    except ConversationNotFoundError as exc:
        await db.rollback()
        raise api_error(404, "CONVERSATION_NOT_FOUND", "未找到该组卷会话。") from exc
    except ConversationGraphBusyError as exc:
        await db.rollback()
        raise api_error(
            409,
            "CONFIRMATION_REQUIRED",
            "请先处理当前待确认操作，再修改方案。",
        ) from exc
    except ConversationGraphClosedError as exc:
        await db.rollback()
        raise api_error(
            409,
            "CONVERSATION_COMPLETED",
            "该会话已生成试卷，请新建会话后再组另一张试卷。",
        ) from exc
    except ValueError as exc:
        await db.rollback()
        raise api_error(
            409,
            "MESSAGE_CONFLICT",
            "该消息编号已用于其他内容，请刷新后重试。",
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise api_error(
            409,
            "PLAN_CONFLICT",
            "该方案修改已提交，请刷新后查看。",
        ) from exc


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationGraphStatusResponse,
)
async def submit_message_endpoint(
    conversation_id: ConversationId,
    payload: ConversationMessageCreate,
    db: AsyncSession = Depends(get_db),
    graph: Any = Depends(get_conversation_graph),
) -> ConversationGraphStatusResponse:
    try:
        return await submit_conversation_message(db, graph, conversation_id, payload)
    except ConversationNotFoundError as exc:
        await db.rollback()
        raise api_error(404, "CONVERSATION_NOT_FOUND", "未找到该组卷会话。") from exc
    except ConversationGraphBusyError as exc:
        raise api_error(
            409,
            "CONFIRMATION_REQUIRED",
            "当前方案正在等待确认，请先确认或取消后再发送新消息。",
        ) from exc
    except ConversationGraphClosedError as exc:
        await db.rollback()
        raise api_error(
            409,
            "CONVERSATION_COMPLETED",
            "该会话已生成试卷，请新建会话后再组另一张试卷。",
        ) from exc
    except ValueError as exc:
        await db.rollback()
        raise api_error(
            409,
            "MESSAGE_CONFLICT",
            "该消息编号已用于其他内容，请刷新后重试。",
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise api_error(
            409,
            "MESSAGE_CONFLICT",
            "该消息编号已被使用，请勿重复提交不同内容。",
        ) from exc


@router.get(
    "/{conversation_id}/status",
    response_model=ConversationGraphStatusResponse | None,
)
async def get_status_endpoint(
    conversation_id: ConversationId,
    db: AsyncSession = Depends(get_db),
    graph: Any = Depends(get_conversation_graph),
) -> ConversationGraphStatusResponse | None:
    try:
        return await get_conversation_status(db, graph, conversation_id)
    except ConversationNotFoundError as exc:
        raise api_error(404, "CONVERSATION_NOT_FOUND", "未找到该组卷会话。") from exc


@router.post(
    "/{conversation_id}/{action}",
    response_model=ConversationGraphStatusResponse,
)
async def command_endpoint(
    conversation_id: ConversationId,
    action: Literal["confirm", "cancel", "retry"],
    db: AsyncSession = Depends(get_db),
    graph: Any = Depends(get_conversation_graph),
) -> ConversationGraphStatusResponse:
    try:
        return await command_conversation(
            db,
            graph,
            conversation_id,
            ConversationGraphCommand(action=action),
        )
    except (ConversationNotFoundError, ConversationGraphNotFoundError) as exc:
        raise api_error(404, "CONVERSATION_NOT_FOUND", "未找到该组卷会话。") from exc
    except ConversationGraphNotInterruptedError as exc:
        raise api_error(
            409,
            "ACTION_NOT_PENDING",
            "当前没有等待确认的组卷操作。",
        ) from exc
    except (ConversationGraphBusyError, ValueError) as exc:
        raise api_error(
            409,
            "ACTION_CONFLICT",
            "该操作已处理或与当前状态不匹配。",
        ) from exc

"""Production handlers and checkpoint services for the conversation graph."""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.types import Command
from sqlalchemy import select

from app.database import async_session
from app.models import ConversationModel, PendingActionModel
from app.modules.paper_agent.graph.conversation_workflow import (
    ConversationWorkflowHandlers,
)
from app.modules.paper_agent.schemas.conversation import (
    MessageRole,
    PendingActionStatus,
    PendingActionType,
)
from app.modules.paper_agent.schemas.conversation_agent import (
    ConversationAgentOutcomeKind,
)
from app.modules.paper_agent.schemas.conversation_graph import (
    ConversationGraphCommand,
    ConversationGraphReport,
    ConversationGraphState,
    ConversationGraphStatus,
    ConversationGraphStatusResponse,
)
from app.modules.paper_agent.schemas.tools import CreatePaperToolInput
from app.modules.paper_agent.services.conversation_agent import (
    run_conversation_agent,
)
from app.modules.paper_agent.services.conversation_store import (
    append_message,
    create_pending_action,
    load_message,
    load_plan,
    save_plan,
    utc_now,
)
from app.modules.paper_agent.services.conversation_tools import (
    ToolContext,
    controlled_tool_executor,
)
from app.modules.paper_agent.services.optimization import optimize_paper


MAX_CONVERSATION_RETRIES = 2
ACTION_CONFIRMATION_SUMMARIES = {
    "lock_questions": "已准备锁题变更，等待教师确认后执行。",
    "replace_question": "已准备换题操作，等待教师确认后执行。",
    "reassemble_paper": "已准备重新组卷，等待教师确认后执行。",
    "submit_review": "已准备提交审核结论，等待教师确认后执行。",
    "prepare_exports": "已准备生成下载文件，等待教师确认后执行。",
    "apply_taxonomy_change": "已准备标签体系变更，等待确认后写入。",
    "deactivate_taxonomy_item": "已准备停用标签，等待确认后执行。",
}
ACTION_COMPLETION_SUMMARIES = {
    "create_paper": "组卷任务已创建并进入教师审核。",
    "lock_questions": "锁题状态已更新。",
    "replace_question": "指定题目已替换，试卷约束仍然有效。",
    "reassemble_paper": "试卷已按当前锁题和约束重新生成。",
    "submit_review": "教师审核结果已提交。",
    "prepare_exports": "试卷文档已经准备好，可以进入任务详情下载。",
    "apply_taxonomy_change": "标签体系变更已完成。",
    "deactivate_taxonomy_item": "标签已停用，历史引用仍然保留。",
}


class ConversationGraphBusyError(RuntimeError):
    pass


class ConversationGraphNotFoundError(LookupError):
    pass


class ConversationGraphNotInterruptedError(RuntimeError):
    pass


class ConversationGraphClosedError(RuntimeError):
    pass


def conversation_thread_id(conversation_id: str) -> str:
    return f"paper-conversation:{conversation_id}"


def conversation_thread_config(conversation_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": conversation_thread_id(conversation_id)}}


def _deterministic_id(namespace: str, value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"flowgate:{namespace}:{value}"))


def _report(
    state: ConversationGraphState,
    code: str,
    summary: str,
    **details: str | int | float | bool | None,
) -> list[ConversationGraphReport]:
    return [
        *state.reports,
        ConversationGraphReport(
            code=code,
            summary=summary[:1000],
            details=details,
        ),
    ]


def _action_confirmation_summary(
    tool_name: str,
    payload: dict[str, Any],
) -> str:
    if tool_name == "apply_taxonomy_change":
        change = payload.get("change", {})
        action_labels = {
            "create_module": "新增课程模块",
            "update_module": "修改课程模块",
            "create_knowledge_point": "新增知识点",
            "update_knowledge_point": "修改知识点",
        }
        label = action_labels.get(change.get("action"), "修改标签体系")
        target = " ".join(
            value for value in (change.get("code"), change.get("name")) if value
        )
        location = ""
        if change.get("module_code"):
            location = f"；所属模块 {change['module_code']}"
        if change.get("parent_code"):
            location += f"；父知识点 {change['parent_code']}"
        return f"准备{label}：{target}{location}。确认后将写入标签体系。"
    if tool_name == "deactivate_taxonomy_item":
        entity = "课程模块" if payload.get("entity_type") == "module" else "知识点"
        return f"准备停用{entity}：{payload.get('code', '')}。确认后执行，历史题目引用不会删除。"
    return ACTION_CONFIRMATION_SUMMARIES[tool_name]


async def _parse_and_merge(state: ConversationGraphState) -> ConversationGraphState:
    if (
        state.plan_version is not None
        and state.status == ConversationGraphStatus.CHECKING_FEASIBILITY
    ):
        return state
    async with async_session() as session:
        message = await load_message(
            session,
            state.conversation_id,
            state.message_id,
        )
        previous_plan = await load_plan(session, state.conversation_id)
        outcome = await run_conversation_agent(
            session,
            state.conversation_id,
            previous_plan=previous_plan,
        )
        if outcome.kind == ConversationAgentOutcomeKind.PLAN:
            plan_version = await save_plan(
                session,
                conversation_id=state.conversation_id,
                source_message_id=state.message_id,
                plan=outcome.plan,
            )
            await session.commit()
            return state.model_copy(
                update={
                    "plan_version": plan_version,
                    "status": ConversationGraphStatus.CHECKING_FEASIBILITY,
                    "reports": _report(
                        state,
                        "plan_ready",
                        "组卷参数已解析并通过结构校验。",
                    ),
                }
            )
        if outcome.kind == ConversationAgentOutcomeKind.WRITE_ACTION:
            definition = controlled_tool_executor.registry.get(outcome.tool_name)
            if definition.action_type is None:
                raise ValueError("read tool cannot create a pending action")
            action_id = _deterministic_id(
                "agent-write-action",
                f"{state.conversation_id}:{state.message_id}:{outcome.tool_name}",
            )
            conversation = await session.get(ConversationModel, state.conversation_id)
            await create_pending_action(
                session,
                action_id=action_id,
                conversation_id=state.conversation_id,
                action_type=definition.action_type,
                source_message_id=state.message_id,
                plan_version=(
                    conversation.active_plan_version
                    if conversation.active_plan_version > 0
                    else None
                ),
                request_payload=outcome.tool_payload,
            )
            await session.commit()
            return state.model_copy(
                update={
                    "plan_version": (
                        conversation.active_plan_version
                        if conversation.active_plan_version > 0
                        else None
                    ),
                    "pending_action_id": action_id,
                    "paper_job_id": conversation.paper_job_id,
                    "status": ConversationGraphStatus.AWAITING_CONFIRMATION,
                    "reports": _report(
                        state,
                        "agent_action_ready",
                        _action_confirmation_summary(
                            outcome.tool_name,
                            outcome.tool_payload,
                        ),
                        tool_name=outcome.tool_name,
                    ),
                }
            )
        status_by_kind = {
            ConversationAgentOutcomeKind.REPLY: ConversationGraphStatus.RESPONDED,
            ConversationAgentOutcomeKind.NEEDS_INPUT: ConversationGraphStatus.NEEDS_INPUT,
            ConversationAgentOutcomeKind.FORM_FALLBACK: ConversationGraphStatus.FORM_FALLBACK,
        }
        status = status_by_kind[outcome.kind]
        return state.model_copy(
            update={
                "status": status,
                "reports": _report(
                    state,
                    "agent_reply",
                    outcome.reply,
                    form_fallback=(
                        outcome.kind == ConversationAgentOutcomeKind.FORM_FALLBACK
                    ),
                ),
            }
        )


async def _check_feasibility(state: ConversationGraphState) -> ConversationGraphState:
    async with async_session() as session:
        plan = await load_plan(
            session,
            state.conversation_id,
            state.plan_version,
        )
        try:
            result = await optimize_paper(session, plan.optimization)
        except Exception as exc:
            return state.model_copy(
                update={
                    "status": ConversationGraphStatus.INFEASIBLE,
                    "reports": _report(
                        state,
                        "plan_infeasible",
                        "当前题库无法在不放宽约束的前提下完成这份试卷，请修改题型、难度或知识点范围。",
                        error_type=type(exc).__name__,
                    ),
                }
            )
        return state.model_copy(
            update={
                "status": ConversationGraphStatus.CHECKING_FEASIBILITY,
                "reports": _report(
                    state,
                    "plan_feasible",
                    "题库能够满足当前组卷约束。",
                    candidate_question_count=result.question_count,
                ),
            }
        )


async def _prepare_confirmation(state: ConversationGraphState) -> ConversationGraphState:
    action_id = _deterministic_id(
        "create-paper-action",
        f"{state.conversation_id}:{state.plan_version}:{state.retry_count}",
    )
    async with async_session() as session:
        action = await session.get(PendingActionModel, action_id)
        if action is None:
            plan = await load_plan(
                session,
                state.conversation_id,
                state.plan_version,
            )
            payload = CreatePaperToolInput(plan=plan).model_dump(mode="json")
            await create_pending_action(
                session,
                action_id=action_id,
                conversation_id=state.conversation_id,
                action_type=PendingActionType.CREATE_PAPER,
                source_message_id=state.message_id,
                plan_version=state.plan_version,
                request_payload=payload,
            )
            await session.commit()
    return state.model_copy(
        update={
            "pending_action_id": action_id,
            "status": ConversationGraphStatus.AWAITING_CONFIRMATION,
            "reports": _report(
                state,
                f"confirmation_ready_{state.retry_count}",
                "组卷方案已准备好，等待教师确认后执行。",
                retry_count=state.retry_count,
            ),
        }
    )


async def _apply_command(
    state: ConversationGraphState,
    command: ConversationGraphCommand,
) -> ConversationGraphState:
    async with async_session() as session:
        action = await session.scalar(
            select(PendingActionModel)
            .where(PendingActionModel.action_id == state.pending_action_id)
            .with_for_update()
        )
        if action is None or action.conversation_id != state.conversation_id:
            raise ConversationGraphNotFoundError(state.pending_action_id)
        if command.action == "cancel":
            if action.status == PendingActionStatus.PENDING.value:
                action.status = PendingActionStatus.CANCELLED.value
                action.completed_at = utc_now()
                action.updated_at = utc_now()
                await session.commit()
            return state.model_copy(update={"status": ConversationGraphStatus.CANCELLED})
        if command.action == "retry" and state.retry_count == 0:
            raise ValueError("retry is only available after a failed execution")
        if action.status == PendingActionStatus.PENDING.value:
            action.status = PendingActionStatus.CONFIRMED.value
            action.confirmed_at = utc_now()
            action.updated_at = utc_now()
            await session.commit()
        elif action.status == PendingActionStatus.COMPLETED.value:
            result = action.result_payload or {}
            summary = result.get("message") or "操作已经完成。"
            return state.model_copy(
                update={
                    "paper_job_id": action.paper_job_id or state.paper_job_id,
                    "status": ConversationGraphStatus.COMPLETED,
                    "reports": _report(
                        state,
                        "agent_operation_already_completed",
                        summary,
                        action_type=action.action_type,
                    ),
                }
            )
        elif action.status != PendingActionStatus.CONFIRMED.value:
            raise ConversationGraphBusyError(action.status)
    return state.model_copy(update={"status": ConversationGraphStatus.EXECUTING})


async def _execute_with_graph(
    state: ConversationGraphState,
    review_graph: Any,
) -> ConversationGraphState:
    async with async_session() as session:
        action = await session.get(PendingActionModel, state.pending_action_id)
        if action is None:
            raise ConversationGraphNotFoundError(state.pending_action_id)
        tool_name = next(
            (
                name
                for name in controlled_tool_executor.registry.names
                if controlled_tool_executor.registry.get(name).action_type is not None
                and controlled_tool_executor.registry.get(name).action_type.value
                == action.action_type
            ),
            None,
        )
        if tool_name is None:
            raise ConversationGraphNotFoundError(action.action_type)
        try:
            result = await controlled_tool_executor.execute(
                tool_name,
                action.request_payload,
                ToolContext(
                    session=session,
                    review_graph=review_graph,
                    conversation_id=state.conversation_id,
                ),
                action_id=state.pending_action_id,
            )
        except Exception as exc:
            retryable = isinstance(exc, (ConnectionError, TimeoutError))
            if retryable and state.retry_count < MAX_CONVERSATION_RETRIES:
                return state.model_copy(
                    update={
                        "status": ConversationGraphStatus.RETRYABLE,
                        "reports": _report(
                            state,
                            f"execution_failed_{state.retry_count}",
                            "操作执行暂时失败，可以在确认后重试。",
                            error_type=type(exc).__name__,
                        ),
                    }
                )
            return state.model_copy(
                update={
                    "status": ConversationGraphStatus.FAILED,
                    "error_code": "AGENT_OPERATION_FAILED",
                    "reports": _report(
                        state,
                        "execution_failed_final",
                        "操作执行失败，请根据错误信息调整后重试。",
                        error_type=type(exc).__name__,
                    ),
                }
            )
        conversation = await session.get(ConversationModel, state.conversation_id)
        result_job_id = result.get("job_id")
        if result_job_id is not None:
            conversation.paper_job_id = result_job_id
            conversation.updated_at = utc_now()
        await session.commit()
        summary = result.get("message") or ACTION_COMPLETION_SUMMARIES[tool_name]
        return state.model_copy(
            update={
                "paper_job_id": result_job_id or conversation.paper_job_id,
                "status": ConversationGraphStatus.COMPLETED,
                    "reports": _report(
                        state,
                        "agent_operation_completed",
                        summary,
                        tool_name=tool_name,
                    ),
                }
            )


async def _prepare_retry(state: ConversationGraphState) -> ConversationGraphState:
    retry_count = state.retry_count + 1
    action_id = _deterministic_id(
        "agent-action-retry",
        f"{state.pending_action_id}:{retry_count}",
    )
    async with async_session() as session:
        previous = await session.get(PendingActionModel, state.pending_action_id)
        if previous is None:
            raise ConversationGraphNotFoundError(state.pending_action_id)
        action = await session.get(PendingActionModel, action_id)
        if action is None:
            await create_pending_action(
                session,
                action_id=action_id,
                conversation_id=state.conversation_id,
                action_type=PendingActionType(previous.action_type),
                source_message_id=previous.source_message_id,
                plan_version=previous.plan_version,
                request_payload=previous.request_payload,
            )
            await session.commit()
    return state.model_copy(
        update={
            "pending_action_id": action_id,
            "retry_count": retry_count,
            "status": ConversationGraphStatus.AWAITING_CONFIRMATION,
            "reports": _report(
                state,
                f"retry_ready_{retry_count}",
                "原操作已准备重试，等待再次确认。",
                retry_count=retry_count,
            ),
        }
    )


def _assistant_summary(state: ConversationGraphState) -> str:
    if state.status == ConversationGraphStatus.COMPLETED:
        if state.reports:
            return state.reports[-1].summary
        return f"操作已完成，任务编号：{state.paper_job_id}。"
    if state.status == ConversationGraphStatus.CANCELLED:
        return "已取消本次操作，现有数据没有改变。"
    if state.status == ConversationGraphStatus.FAILED:
        return "操作执行失败，现有数据没有改变，请调整请求后重试。"
    if state.reports:
        return state.reports[-1].summary
    return "本轮对话已处理。"


async def _finish(state: ConversationGraphState) -> ConversationGraphState:
    assistant_id = _deterministic_id(
        "assistant-message",
        f"{state.message_id}:{state.status.value}:{state.retry_count}",
    )
    async with async_session() as session:
        await append_message(
            session,
            message_id=assistant_id,
            conversation_id=state.conversation_id,
            role=MessageRole.ASSISTANT,
            content=_assistant_summary(state),
            attributes={
                "status": state.status.value,
                "plan_version": state.plan_version,
                "paper_job_id": state.paper_job_id,
            },
        )
        await session.commit()
    return state


def build_conversation_workflow_handlers(review_graph: Any) -> ConversationWorkflowHandlers:
    async def execute(state: ConversationGraphState) -> ConversationGraphState:
        return await _execute_with_graph(state, review_graph)

    return ConversationWorkflowHandlers(
        parse_and_merge=_parse_and_merge,
        check_feasibility=_check_feasibility,
        prepare_confirmation=_prepare_confirmation,
        apply_command=_apply_command,
        execute=execute,
        prepare_retry=_prepare_retry,
        finish=_finish,
    )


async def get_conversation_graph_status(
    graph: Any,
    conversation_id: str,
) -> ConversationGraphStatusResponse | None:
    snapshot = await graph.aget_state(conversation_thread_config(conversation_id))
    if not snapshot.values:
        return None
    state = ConversationGraphState.model_validate(snapshot.values)
    return ConversationGraphStatusResponse(
        state=state,
        interrupted=bool(snapshot.interrupts),
        interrupt_payload=(snapshot.interrupts[0].value if snapshot.interrupts else None),
    )


async def start_conversation_turn(
    graph: Any,
    conversation_id: str,
    message_id: str,
) -> ConversationGraphStatusResponse:
    existing = await get_conversation_graph_status(graph, conversation_id)
    if existing is not None and existing.state.message_id == message_id:
        return existing
    if existing is not None and existing.interrupted:
        raise ConversationGraphBusyError(existing.state.pending_action_id)
    initial = ConversationGraphState(
        conversation_id=conversation_id,
        message_id=message_id,
    )
    await graph.ainvoke(initial, config=conversation_thread_config(conversation_id))
    result = await get_conversation_graph_status(graph, conversation_id)
    if result is None:
        raise RuntimeError("conversation graph did not persist state")
    return result


async def start_conversation_plan_turn(
    graph: Any,
    conversation_id: str,
    message_id: str,
    plan_version: int,
) -> ConversationGraphStatusResponse:
    existing = await get_conversation_graph_status(graph, conversation_id)
    if existing is not None and existing.state.message_id == message_id:
        return existing
    if existing is not None and existing.interrupted:
        raise ConversationGraphBusyError(existing.state.pending_action_id)
    initial = ConversationGraphState(
        conversation_id=conversation_id,
        message_id=message_id,
        plan_version=plan_version,
        status=ConversationGraphStatus.CHECKING_FEASIBILITY,
    )
    await graph.ainvoke(initial, config=conversation_thread_config(conversation_id))
    result = await get_conversation_graph_status(graph, conversation_id)
    if result is None:
        raise RuntimeError("conversation graph did not persist form plan state")
    return result


async def resume_conversation_turn(
    graph: Any,
    conversation_id: str,
    command: ConversationGraphCommand,
) -> ConversationGraphStatusResponse:
    existing = await get_conversation_graph_status(graph, conversation_id)
    if existing is None:
        raise ConversationGraphNotFoundError(conversation_id)
    if not existing.interrupted:
        raise ConversationGraphNotInterruptedError(existing.state.status.value)
    await graph.ainvoke(
        Command(resume=command.model_dump(mode="json")),
        config=conversation_thread_config(conversation_id),
    )
    result = await get_conversation_graph_status(graph, conversation_id)
    if result is None:
        raise RuntimeError("conversation graph lost persisted state")
    return result


__all__ = [
    "ConversationGraphBusyError",
    "ConversationGraphClosedError",
    "ConversationGraphNotFoundError",
    "ConversationGraphNotInterruptedError",
    "MAX_CONVERSATION_RETRIES",
    "build_conversation_workflow_handlers",
    "conversation_thread_config",
    "conversation_thread_id",
    "get_conversation_graph_status",
    "resume_conversation_turn",
    "start_conversation_turn",
    "start_conversation_plan_turn",
]

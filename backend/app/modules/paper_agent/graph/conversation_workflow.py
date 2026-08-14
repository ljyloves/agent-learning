"""LangGraph workflow for multi-turn conversational paper generation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.modules.paper_agent.schemas.conversation_graph import (
    ConversationGraphCommand,
    ConversationGraphState,
    ConversationGraphStatus,
)


StateHandler = Callable[[ConversationGraphState], Awaitable[ConversationGraphState]]
CommandHandler = Callable[
    [ConversationGraphState, ConversationGraphCommand],
    Awaitable[ConversationGraphState],
]


@dataclass(frozen=True, slots=True)
class ConversationWorkflowHandlers:
    parse_and_merge: StateHandler
    check_feasibility: StateHandler
    prepare_confirmation: StateHandler
    apply_command: CommandHandler
    execute: StateHandler
    prepare_retry: StateHandler
    finish: StateHandler


def _validated(handler: StateHandler) -> StateHandler:
    @wraps(handler)
    async def wrapper(state: Any) -> ConversationGraphState:
        validated = ConversationGraphState.model_validate(state)
        return ConversationGraphState.model_validate(await handler(validated))

    return wrapper


def _route_after_parse(state: Any) -> str:
    status = ConversationGraphState.model_validate(state).status
    if status == ConversationGraphStatus.CHECKING_FEASIBILITY:
        return "check_feasibility"
    if status == ConversationGraphStatus.AWAITING_CONFIRMATION:
        return "await_confirmation"
    return "finish"


def _route_after_feasibility(state: Any) -> str:
    status = ConversationGraphState.model_validate(state).status
    if status == ConversationGraphStatus.CHECKING_FEASIBILITY:
        return "prepare_confirmation"
    return "finish"


def _route_after_command(state: Any) -> str:
    status = ConversationGraphState.model_validate(state).status
    if status == ConversationGraphStatus.EXECUTING:
        return "execute"
    return "finish"


def _route_after_execute(state: Any) -> str:
    status = ConversationGraphState.model_validate(state).status
    if status == ConversationGraphStatus.RETRYABLE:
        return "prepare_retry"
    return "finish"


def build_conversation_agent_graph(
    handlers: ConversationWorkflowHandlers,
    checkpointer: BaseCheckpointSaver | None = None,
):
    graph = StateGraph(ConversationGraphState)
    graph.add_node("parse_and_merge", _validated(handlers.parse_and_merge))
    graph.add_node("check_feasibility", _validated(handlers.check_feasibility))
    graph.add_node(
        "prepare_confirmation",
        _validated(handlers.prepare_confirmation),
    )

    async def await_confirmation(state: Any) -> ConversationGraphState:
        validated = ConversationGraphState.model_validate(state)
        raw_command = interrupt(
            {
                "kind": "paper_plan_confirmation",
                "conversation_id": validated.conversation_id,
                "plan_version": validated.plan_version,
                "action_id": validated.pending_action_id,
                "retry": validated.retry_count > 0,
            }
        )
        command = ConversationGraphCommand.model_validate(raw_command)
        return ConversationGraphState.model_validate(
            await handlers.apply_command(validated, command)
        )

    graph.add_node("await_confirmation", await_confirmation)
    graph.add_node("execute", _validated(handlers.execute))
    graph.add_node("prepare_retry", _validated(handlers.prepare_retry))
    graph.add_node("finish", _validated(handlers.finish))

    graph.add_edge(START, "parse_and_merge")
    graph.add_conditional_edges(
        "parse_and_merge",
        _route_after_parse,
        {
            "check_feasibility": "check_feasibility",
            "await_confirmation": "await_confirmation",
            "finish": "finish",
        },
    )
    graph.add_conditional_edges(
        "check_feasibility",
        _route_after_feasibility,
        {
            "prepare_confirmation": "prepare_confirmation",
            "finish": "finish",
        },
    )
    graph.add_edge("prepare_confirmation", "await_confirmation")
    graph.add_conditional_edges(
        "await_confirmation",
        _route_after_command,
        {"execute": "execute", "finish": "finish"},
    )
    graph.add_conditional_edges(
        "execute",
        _route_after_execute,
        {"prepare_retry": "prepare_retry", "finish": "finish"},
    )
    graph.add_edge("prepare_retry", "await_confirmation")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["ConversationWorkflowHandlers", "build_conversation_agent_graph"]

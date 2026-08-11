"""Application service for starting and resuming checkpointed graph tasks."""

from __future__ import annotations

from typing import Any

from langgraph.types import Command

from app.modules.paper_agent.graph.state import PaperGraphReport, PaperGraphState
from app.modules.paper_agent.schemas.checkpoint import (
    PaperGraphDecisionRequest,
    PaperGraphTaskResume,
    PaperGraphTaskStart,
    TeacherReviewCommand,
    TeacherReviewTaskStart,
)
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus


class GraphTaskAlreadyExistsError(RuntimeError):
    pass


class GraphTaskNotFoundError(RuntimeError):
    pass


class GraphTaskNotResumableError(RuntimeError):
    pass


class TeacherReviewAlreadyExistsError(RuntimeError):
    pass


class TeacherReviewNotFoundError(RuntimeError):
    pass


class TeacherReviewNotPendingError(RuntimeError):
    pass


def graph_thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def teacher_review_thread_id(thread_id: str) -> str:
    return f"teacher-review:{thread_id}"


def teacher_review_thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    return graph_thread_config(teacher_review_thread_id(thread_id))


def _quality_gate_report(
    request: PaperGraphDecisionRequest,
    attempt: int,
) -> PaperGraphReport:
    metrics: dict[str, str] = {"decision": request.decision.value}
    if request.error_code is not None:
        metrics["error_code"] = request.error_code
    if request.replace_question_id is not None:
        metrics["replace_question_id"] = request.replace_question_id
    if request.replacement_question_id is not None:
        metrics["replacement_question_id"] = request.replacement_question_id
    return PaperGraphReport(
        report_id=f"quality-gate:{attempt}",
        stage="quality_gate",
        summary=f"Quality gate requested {request.decision.value}.",
        metrics=metrics,
    )


async def get_graph_task_state(graph: Any, thread_id: str) -> PaperGraphState | None:
    snapshot = await graph.aget_state(graph_thread_config(thread_id))
    if not snapshot.values:
        return None
    return PaperGraphState.model_validate(snapshot.values)


async def start_graph_task(
    graph: Any,
    thread_id: str,
    request: PaperGraphTaskStart,
) -> PaperGraphState:
    if await get_graph_task_state(graph, thread_id) is not None:
        raise GraphTaskAlreadyExistsError(thread_id)

    initial_state = PaperGraphState(
        job_id=request.job_id,
        paper_id=request.paper_id,
        candidate_question_ids=request.candidate_question_ids,
        selected_question_ids=request.selected_question_ids,
        reports=[_quality_gate_report(request, attempt=1)],
    )
    result = await graph.ainvoke(
        initial_state,
        config=graph_thread_config(thread_id),
    )
    return PaperGraphState.model_validate(result)


async def resume_graph_task(
    graph: Any,
    thread_id: str,
    request: PaperGraphTaskResume,
) -> PaperGraphState:
    state = await get_graph_task_state(graph, thread_id)
    if state is None:
        raise GraphTaskNotFoundError(thread_id)
    if state.execution.status != PaperJobStatus.QUEUED:
        raise GraphTaskNotResumableError(state.execution.status.value)

    next_attempt = state.execution.attempt + 1
    resumed_state = state.model_copy(
        update={
            "reports": [
                *state.reports,
                _quality_gate_report(request, attempt=next_attempt),
            ]
        }
    )
    result = await graph.ainvoke(
        resumed_state,
        config=graph_thread_config(thread_id),
    )
    return PaperGraphState.model_validate(result)


async def get_teacher_review_state(
    graph: Any,
    thread_id: str,
) -> PaperGraphState | None:
    snapshot = await graph.aget_state(teacher_review_thread_config(thread_id))
    if not snapshot.values:
        return None
    return PaperGraphState.model_validate(snapshot.values)


async def start_teacher_review(
    graph: Any,
    thread_id: str,
    request: TeacherReviewTaskStart,
) -> PaperGraphState:
    if await get_teacher_review_state(graph, thread_id) is not None:
        raise TeacherReviewAlreadyExistsError(thread_id)

    initial_state = PaperGraphState(
        job_id=request.job_id,
        paper_id=request.paper_id,
        candidate_question_ids=request.candidate_question_ids,
        selected_question_ids=request.selected_question_ids,
    )
    await graph.ainvoke(
        initial_state,
        config=teacher_review_thread_config(thread_id),
    )
    state = await get_teacher_review_state(graph, thread_id)
    if state is None:
        raise RuntimeError("teacher review graph did not persist state")
    return state


async def submit_teacher_review(
    graph: Any,
    thread_id: str,
    request: TeacherReviewCommand,
) -> PaperGraphState:
    state = await get_teacher_review_state(graph, thread_id)
    if state is None:
        raise TeacherReviewNotFoundError(thread_id)
    if state.execution.status != PaperJobStatus.AWAITING_REVIEW:
        raise TeacherReviewNotPendingError(state.execution.status.value)

    await graph.ainvoke(
        Command(resume=request.model_dump(mode="json")),
        config=teacher_review_thread_config(thread_id),
    )
    resumed_state = await get_teacher_review_state(graph, thread_id)
    if resumed_state is None:
        raise RuntimeError("teacher review graph lost persisted state")
    return resumed_state

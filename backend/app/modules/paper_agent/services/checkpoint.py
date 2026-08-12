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


async def sync_teacher_review_selection(
    graph: Any,
    thread_id: str,
    selected_question_ids: list[str],
    *,
    operation: str,
    actor: str,
    comment: str | None,
    locked_count: int,
) -> PaperGraphState:
    """Replace the selected ID set while preserving an active review interrupt."""

    state = await get_teacher_review_state(graph, thread_id)
    if state is None:
        raise TeacherReviewNotFoundError(thread_id)
    if state.execution.status != PaperJobStatus.AWAITING_REVIEW:
        raise TeacherReviewNotPendingError(state.execution.status.value)
    if len(selected_question_ids) != len(state.selected_question_ids):
        raise ValueError("selection sync must preserve the paper question count")
    if not set(selected_question_ids).issubset(state.candidate_question_ids):
        raise ValueError("selection sync contains a non-candidate question")

    changed_count = len(
        set(selected_question_ids) ^ set(state.selected_question_ids)
    ) // 2
    replacement_count = state.execution.replacement_count + changed_count
    report = PaperGraphReport(
        report_id=(
            f"selection-sync:{replacement_count}:{len(state.reports) + 1}"
        ),
        stage="teacher_review_sync",
        summary=f"Teacher {operation} updated the optimized paper selection.",
        metrics={
            "operation": operation,
            "actor": actor,
            "comment": comment,
            "changed_count": changed_count,
            "locked_count": locked_count,
        },
    )
    updated = PaperGraphState.model_validate(
        state.model_copy(
            update={
                "selected_question_ids": selected_question_ids,
                "reports": [*state.reports, report],
                "execution": state.execution.model_copy(
                    update={"replacement_count": replacement_count}
                ),
            }
        )
    )
    await graph.aupdate_state(
        teacher_review_thread_config(thread_id),
        updated.model_dump(mode="python"),
    )
    persisted = await get_teacher_review_state(graph, thread_id)
    if persisted is None:
        raise RuntimeError("teacher review graph lost synchronized state")
    return persisted

"""Persisted optimized-paper revisions with locks and checkpoint synchronization."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PaperJobModel, PaperJobQuestionModel
from app.modules.paper_agent.schemas.checkpoint import (
    TeacherReviewCommand,
    TeacherReviewTaskStart,
)
from app.modules.paper_agent.schemas.optimization import (
    OptimizedPaperRequest,
    OptimizedPaperResult,
)
from app.modules.paper_agent.schemas.optimized_task import (
    OptimizedPaperLockUpdate,
    OptimizedPaperInfo,
    OptimizedPaperReassemble,
    OptimizedPaperReplace,
    OptimizedPaperTaskCreate,
    OptimizedPaperTaskListItem,
    OptimizedPaperTaskListResponse,
    OptimizedPaperTaskResponse,
    OptimizedPaperTaskReview,
)
from app.modules.paper_agent.schemas.paper_job import (
    PaperJobStatus,
    ReviewResult,
    ReviewStatus,
)
from app.modules.paper_agent.services.checkpoint import (
    get_teacher_review_state,
    start_teacher_review,
    submit_teacher_review,
    sync_teacher_review_selection,
    teacher_review_thread_id,
)
from app.modules.paper_agent.services.optimization import (
    EmbeddingFunction,
    candidate_question_ids_for_optimization,
    optimize_paper,
)
from app.services.embedding import embed


class OptimizedTaskNotFoundError(RuntimeError):
    pass


class OptimizedTaskNotReviewableError(RuntimeError):
    pass


class OptimizedTaskSelectionError(ValueError):
    pass


class LockedQuestionError(ValueError):
    pass


DEFAULT_PAPER_NAME = "未命名高中生物试卷"
DEFAULT_GRADE = "高中"
DEFAULT_EXAM_TYPE = "练习"
DEFAULT_DURATION_MINUTES = 90


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def selected_question_ids(paper: OptimizedPaperResult) -> list[str]:
    return [
        question.question_id
        for section in paper.sections
        for question in section.questions
    ]


async def _delete_review_checkpoint(graph: Any, job_id: str) -> None:
    checkpointer = getattr(graph, "checkpointer", None)
    if checkpointer is not None:
        await checkpointer.adelete_thread(teacher_review_thread_id(job_id))


def _paper(job: PaperJobModel) -> OptimizedPaperResult:
    if job.assembly_result is None:
        raise OptimizedTaskNotFoundError(job.job_id)
    return OptimizedPaperResult.model_validate(job.assembly_result)


def _request(job: PaperJobModel) -> OptimizedPaperRequest:
    if job.assembly_request is None:
        raise OptimizedTaskNotFoundError(job.job_id)
    payload = job.assembly_request
    if "optimization" in payload:
        payload = payload["optimization"]
    return OptimizedPaperRequest.model_validate(payload)


def _paper_info(job: PaperJobModel) -> OptimizedPaperInfo:
    payload = job.assembly_request or {}
    raw_info = payload.get("paper_info") if isinstance(payload, dict) else None
    return OptimizedPaperInfo.model_validate(raw_info or {})


def _assembly_request_payload(
    request: OptimizedPaperRequest,
    paper_info: OptimizedPaperInfo | None,
) -> dict[str, Any]:
    return {
        "optimization": request.model_dump(mode="json"),
        "paper_info": (paper_info or OptimizedPaperInfo()).model_dump(
            mode="json",
            exclude_none=True,
        ),
    }


def _list_item(job: PaperJobModel) -> OptimizedPaperTaskListItem:
    request = _request(job)
    paper_info = _paper_info(job)
    return OptimizedPaperTaskListItem(
        job_id=job.job_id,
        paper_name=paper_info.paper_name or DEFAULT_PAPER_NAME,
        grade=paper_info.grade or DEFAULT_GRADE,
        exam_type=paper_info.exam_type or DEFAULT_EXAM_TYPE,
        duration_minutes=(
            paper_info.duration_minutes or DEFAULT_DURATION_MINUTES
        ),
        question_count=request.question_count,
        total_score=request.total_score,
        status=job.status,
        review_status=job.review_status,
        awaiting_teacher=job.status == PaperJobStatus.AWAITING_REVIEW.value,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def _locked_question_ids(
    session: AsyncSession,
    job_id: str,
) -> set[str]:
    return set(
        await session.scalars(
            select(PaperJobQuestionModel.question_id).where(
                PaperJobQuestionModel.job_id == job_id,
                PaperJobQuestionModel.is_locked.is_(True),
            )
        )
    )


async def _task_response(
    session: AsyncSession,
    job: PaperJobModel,
) -> OptimizedPaperTaskResponse:
    paper = _paper(job)
    locked = await _locked_question_ids(session, job.job_id)
    return OptimizedPaperTaskResponse(
        job_id=job.job_id,
        generation_mode="optimized",
        status=job.status,
        review_status=job.review_status,
        review_result=(
            ReviewResult.model_validate(job.review_result)
            if job.review_result is not None
            else None
        ),
        failure_reason=job.failure_reason,
        awaiting_teacher=job.status == PaperJobStatus.AWAITING_REVIEW.value,
        paper=paper,
        locked_question_ids=[
            question_id
            for question_id in selected_question_ids(paper)
            if question_id in locked
        ],
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def _load_job(
    session: AsyncSession,
    job_id: str,
    *,
    for_update: bool = False,
) -> PaperJobModel:
    statement = select(PaperJobModel).where(PaperJobModel.job_id == job_id)
    if for_update:
        statement = statement.with_for_update()
    job = await session.scalar(statement)
    if job is None or job.generation_mode != "optimized":
        raise OptimizedTaskNotFoundError(job_id)
    _paper(job)
    _request(job)
    return job


def _require_reviewable(job: PaperJobModel) -> None:
    if (
        job.status != PaperJobStatus.AWAITING_REVIEW.value
        or job.review_status != ReviewStatus.PENDING.value
    ):
        raise OptimizedTaskNotReviewableError(job.status)


async def create_optimized_task(
    session: AsyncSession,
    review_graph: Any,
    payload: OptimizedPaperTaskCreate,
    *,
    embedder: EmbeddingFunction = embed,
) -> OptimizedPaperTaskResponse:
    paper = await optimize_paper(
        session,
        payload.optimization,
        embedder=embedder,
    )
    candidate_ids = await candidate_question_ids_for_optimization(
        session,
        payload.optimization,
    )
    if len(candidate_ids) > 1000:
        raise OptimizedTaskSelectionError(
            "optimized task candidate pool exceeds checkpoint limit"
        )
    question_ids = selected_question_ids(paper)
    job_id = str(uuid.uuid4())
    now = utc_now()
    job = PaperJobModel(
        job_id=job_id,
        generation_mode="optimized",
        status=PaperJobStatus.AWAITING_REVIEW.value,
        review_status=ReviewStatus.PENDING.value,
        assembly_request=_assembly_request_payload(
            payload.optimization,
            payload.paper_info,
        ),
        assembly_result=paper.model_dump(mode="json"),
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    review_started = False
    try:
        await session.flush()
        session.add_all(
            [
                PaperJobQuestionModel(
                    job_id=job_id,
                    question_id=question_id,
                    position=position,
                    is_locked=False,
                )
                for position, question_id in enumerate(question_ids)
            ]
        )
        await session.flush()
        state = await start_teacher_review(
            review_graph,
            job_id,
            TeacherReviewTaskStart(
                job_id=job_id,
                paper_id=job_id,
                candidate_question_ids=candidate_ids,
                selected_question_ids=question_ids,
            ),
        )
        review_started = True
        if state.execution.status != PaperJobStatus.AWAITING_REVIEW:
            raise RuntimeError("optimized task did not pause for teacher review")
        await session.commit()
    except Exception:
        await session.rollback()
        if review_started:
            await _delete_review_checkpoint(review_graph, job_id)
        raise
    await session.refresh(job)
    return await _task_response(session, job)


async def get_optimized_task(
    session: AsyncSession,
    job_id: str,
) -> OptimizedPaperTaskResponse:
    job = await _load_job(session, job_id)
    return await _task_response(session, job)


async def list_optimized_tasks(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    status: PaperJobStatus | None = None,
    review_status: ReviewStatus | None = None,
    keyword: str | None = None,
) -> OptimizedPaperTaskListResponse:
    filters = [PaperJobModel.generation_mode == "optimized"]
    if status is not None:
        filters.append(PaperJobModel.status == status.value)
    if review_status is not None:
        filters.append(PaperJobModel.review_status == review_status.value)
    normalized_keyword = keyword.strip() if keyword else None
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        paper_name = PaperJobModel.assembly_request[
            "paper_info"
        ]["paper_name"].astext
        filters.append(
            or_(
                PaperJobModel.job_id.ilike(pattern),
                paper_name.ilike(pattern),
            )
        )

    total = int(
        await session.scalar(
            select(func.count())
            .select_from(PaperJobModel)
            .where(*filters)
        )
        or 0
    )
    jobs = list(
        await session.scalars(
            select(PaperJobModel)
            .where(*filters)
            .order_by(
                PaperJobModel.updated_at.desc(),
                PaperJobModel.job_id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return OptimizedPaperTaskListResponse(
        items=[_list_item(job) for job in jobs],
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


async def update_optimized_task_locks(
    session: AsyncSession,
    job_id: str,
    payload: OptimizedPaperLockUpdate,
) -> OptimizedPaperTaskResponse:
    job = await _load_job(session, job_id, for_update=True)
    _require_reviewable(job)
    relations = list(
        await session.scalars(
            select(PaperJobQuestionModel).where(
                PaperJobQuestionModel.job_id == job_id,
                PaperJobQuestionModel.question_id.in_(payload.question_ids),
            )
        )
    )
    found_ids = {relation.question_id for relation in relations}
    missing_ids = sorted(set(payload.question_ids) - found_ids)
    if missing_ids:
        raise OptimizedTaskSelectionError(
            "only selected questions can be locked or unlocked: "
            + ", ".join(missing_ids)
        )
    for relation in relations:
        relation.is_locked = payload.locked
    job.updated_at = utc_now()
    await session.commit()
    await session.refresh(job)
    return await _task_response(session, job)


async def _review_state(
    review_graph: Any,
    job_id: str,
):
    state = await get_teacher_review_state(review_graph, job_id)
    if state is None:
        raise OptimizedTaskNotReviewableError(
            "teacher review checkpoint is missing"
        )
    if state.execution.status != PaperJobStatus.AWAITING_REVIEW:
        raise OptimizedTaskNotReviewableError(state.execution.status.value)
    return state


async def _replace_relations(
    session: AsyncSession,
    job_id: str,
    paper: OptimizedPaperResult,
    locked_ids: set[str],
) -> None:
    await session.execute(
        delete(PaperJobQuestionModel).where(
            PaperJobQuestionModel.job_id == job_id
        )
    )
    await session.flush()
    session.add_all(
        [
            PaperJobQuestionModel(
                job_id=job_id,
                question_id=question_id,
                position=position,
                is_locked=question_id in locked_ids,
            )
            for position, question_id in enumerate(selected_question_ids(paper))
        ]
    )


async def _persist_revision(
    session: AsyncSession,
    review_graph: Any,
    job: PaperJobModel,
    request: OptimizedPaperRequest,
    old_paper: OptimizedPaperResult,
    new_paper: OptimizedPaperResult,
    locked_ids: set[str],
    *,
    operation: str,
    actor: str,
    comment: str | None,
) -> OptimizedPaperTaskResponse:
    new_ids = selected_question_ids(new_paper)
    if not locked_ids.issubset(new_ids):
        raise LockedQuestionError("optimized revision attempted to replace a locked question")
    await _replace_relations(session, job.job_id, new_paper, locked_ids)
    job.assembly_request = _assembly_request_payload(
        request,
        _paper_info(job),
    )
    job.assembly_result = new_paper.model_dump(mode="json")
    job.updated_at = utc_now()
    await session.flush()

    checkpoint_synced = False
    try:
        await sync_teacher_review_selection(
            review_graph,
            job.job_id,
            new_ids,
            operation=operation,
            actor=actor,
            comment=comment,
            locked_count=len(locked_ids),
        )
        checkpoint_synced = True
        await session.commit()
    except Exception:
        await session.rollback()
        if checkpoint_synced:
            await sync_teacher_review_selection(
                review_graph,
                job.job_id,
                selected_question_ids(old_paper),
                operation="rollback",
                actor="system",
                comment="database revision failed",
                locked_count=len(locked_ids),
            )
        raise
    await session.refresh(job)
    return await _task_response(session, job)


async def replace_optimized_question(
    session: AsyncSession,
    review_graph: Any,
    job_id: str,
    payload: OptimizedPaperReplace,
    *,
    embedder: EmbeddingFunction = embed,
) -> OptimizedPaperTaskResponse:
    job = await _load_job(session, job_id, for_update=True)
    _require_reviewable(job)
    old_paper = _paper(job)
    request = _request(job)
    current_ids = selected_question_ids(old_paper)
    if payload.question_id not in current_ids:
        raise OptimizedTaskSelectionError("question to replace is not selected")
    locked_ids = await _locked_question_ids(session, job_id)
    if payload.question_id in locked_ids:
        raise LockedQuestionError("locked question cannot be replaced")
    state = await _review_state(review_graph, job_id)
    required_ids = set(current_ids) - {payload.question_id}
    if payload.replacement_question_id is not None:
        if payload.replacement_question_id not in state.candidate_question_ids:
            raise OptimizedTaskSelectionError(
                "replacement question is not in the task candidate pool"
            )
        if payload.replacement_question_id in current_ids:
            raise OptimizedTaskSelectionError(
                "replacement question is already selected"
            )
        required_ids.add(payload.replacement_question_id)

    new_paper = await optimize_paper(
        session,
        request,
        embedder=embedder,
        required_question_ids=sorted(required_ids),
        allowed_question_ids=state.candidate_question_ids,
        additional_excluded_question_ids=[payload.question_id],
    )
    new_ids = set(selected_question_ids(new_paper))
    removed_ids = set(current_ids) - new_ids
    added_ids = new_ids - set(current_ids)
    if removed_ids != {payload.question_id} or len(added_ids) != 1:
        raise RuntimeError("single-question replacement changed an invalid selection")
    return await _persist_revision(
        session,
        review_graph,
        job,
        request,
        old_paper,
        new_paper,
        locked_ids,
        operation="replace",
        actor=payload.reviewer,
        comment=payload.comment,
    )


async def reassemble_optimized_task(
    session: AsyncSession,
    review_graph: Any,
    job_id: str,
    payload: OptimizedPaperReassemble,
    *,
    embedder: EmbeddingFunction = embed,
) -> OptimizedPaperTaskResponse:
    job = await _load_job(session, job_id, for_update=True)
    _require_reviewable(job)
    old_paper = _paper(job)
    request_payload = _request(job).model_dump(mode="json")
    current_ids = selected_question_ids(old_paper)
    locked_ids = await _locked_question_ids(session, job_id)
    unlocked_ids = set(current_ids) - locked_ids
    if not unlocked_ids:
        raise LockedQuestionError("all selected questions are locked")
    state = await _review_state(review_graph, job_id)
    request_payload["random_seed"] = (
        payload.random_seed
        if payload.random_seed is not None
        else (request_payload["random_seed"] + 1) % 2_147_483_648
    )
    request = OptimizedPaperRequest.model_validate(request_payload)
    new_paper = await optimize_paper(
        session,
        request,
        embedder=embedder,
        required_question_ids=sorted(locked_ids),
        allowed_question_ids=state.candidate_question_ids,
        additional_excluded_question_ids=sorted(unlocked_ids),
    )
    return await _persist_revision(
        session,
        review_graph,
        job,
        request,
        old_paper,
        new_paper,
        locked_ids,
        operation="reassemble",
        actor=payload.reviewer,
        comment=payload.comment,
    )


async def review_optimized_task(
    session: AsyncSession,
    review_graph: Any,
    job_id: str,
    payload: OptimizedPaperTaskReview,
) -> OptimizedPaperTaskResponse:
    job = await _load_job(session, job_id, for_update=True)
    _require_reviewable(job)
    command = TeacherReviewCommand(
        action=payload.action,
        reviewer=payload.reviewer,
        comment=payload.comment,
    )
    state = await submit_teacher_review(review_graph, job_id, command)
    now = utc_now()
    if payload.action == "approve":
        review_result = ReviewResult(
            status=ReviewStatus.APPROVED,
            reviewer=payload.reviewer,
            comments=payload.comment,
            reviewed_at=now,
        )
        job.status = PaperJobStatus.COMPLETED.value
        job.review_status = ReviewStatus.APPROVED.value
        job.review_result = review_result.model_dump(mode="json")
    else:
        review_result = ReviewResult(
            status=ReviewStatus.REJECTED,
            reviewer=payload.reviewer,
            comments=payload.comment,
            issues=["TEACHER_REJECTED"],
            reviewed_at=now,
        )
        job.status = PaperJobStatus.FAILED.value
        job.failure_reason = payload.comment
        job.review_status = ReviewStatus.REJECTED.value
        job.review_result = review_result.model_dump(mode="json")
    if job.status != state.execution.status.value:
        raise RuntimeError("optimized job and review checkpoint statuses diverged")
    job.updated_at = now
    await session.commit()
    await session.refresh(job)
    return await _task_response(session, job)

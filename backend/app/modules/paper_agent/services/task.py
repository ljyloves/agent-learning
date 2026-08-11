"""Transactional orchestration for persisted paper-generation tasks."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PaperJobModel, PaperJobQuestionModel, QuestionModel
from app.modules.paper_agent.schemas.assembly import PaperAssemblyResult
from app.modules.paper_agent.schemas.checkpoint import (
    TeacherReviewAction,
    TeacherReviewTaskStart,
)
from app.modules.paper_agent.schemas.paper_job import (
    PaperJobStatus,
    ReviewResult,
    ReviewStatus,
)
from app.modules.paper_agent.schemas.task import (
    PaperTaskCreate,
    PaperTaskResponse,
    PaperTaskReview,
)
from app.modules.paper_agent.services.assembly import (
    assemble_paper,
    candidate_question_ids_for_request,
)
from app.modules.paper_agent.services.checkpoint import (
    get_teacher_review_state,
    start_teacher_review,
    submit_teacher_review,
    teacher_review_thread_id,
)


class PaperTaskNotFoundError(RuntimeError):
    pass


class PaperTaskNotReviewableError(RuntimeError):
    pass


class PaperTaskReplacementError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def selected_question_ids(assembly: PaperAssemblyResult) -> list[str]:
    return [
        question.question_id
        for section in assembly.sections
        for question in section.questions
    ]


def task_response(job: PaperJobModel) -> PaperTaskResponse:
    if job.assembly_result is None:
        raise RuntimeError("paper task has no persisted assembly result")
    return PaperTaskResponse(
        job_id=job.job_id,
        status=job.status,
        review_status=job.review_status,
        review_result=(
            ReviewResult.model_validate(job.review_result)
            if job.review_result is not None
            else None
        ),
        failure_reason=job.failure_reason,
        awaiting_teacher=job.status == PaperJobStatus.AWAITING_REVIEW.value,
        assembly=PaperAssemblyResult.model_validate(job.assembly_result),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def _delete_review_checkpoint(graph: Any, job_id: str) -> None:
    checkpointer = getattr(graph, "checkpointer", None)
    if checkpointer is not None:
        await checkpointer.adelete_thread(teacher_review_thread_id(job_id))


async def create_paper_task(
    session: AsyncSession,
    review_graph: Any,
    request: PaperTaskCreate,
) -> PaperTaskResponse:
    assembly = await assemble_paper(session, request.assembly)
    candidate_ids = await candidate_question_ids_for_request(
        session,
        request.assembly,
    )
    question_ids = selected_question_ids(assembly)
    job_id = str(uuid.uuid4())
    now = utc_now()
    job = PaperJobModel(
        job_id=job_id,
        status=PaperJobStatus.AWAITING_REVIEW.value,
        review_status=ReviewStatus.PENDING.value,
        assembly_request=request.assembly.model_dump(mode="json"),
        assembly_result=assembly.model_dump(mode="json"),
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    session.add_all(
        [
            PaperJobQuestionModel(
                job_id=job_id,
                question_id=question_id,
                position=position,
            )
            for position, question_id in enumerate(question_ids)
        ]
    )

    review_started = False
    try:
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
            raise RuntimeError("paper task did not pause for teacher review")
        await session.commit()
    except Exception:
        await session.rollback()
        if review_started:
            await _delete_review_checkpoint(review_graph, job_id)
        raise

    await session.refresh(job)
    return task_response(job)


async def get_paper_task(
    session: AsyncSession,
    job_id: str,
) -> PaperTaskResponse:
    job = await session.get(PaperJobModel, job_id)
    if job is None or job.assembly_result is None:
        raise PaperTaskNotFoundError(job_id)
    return task_response(job)


def _replace_assembly_question(
    assembly: PaperAssemblyResult,
    *,
    old_question_id: str,
    new_question_id: str,
) -> PaperAssemblyResult:
    payload = assembly.model_dump(mode="json")
    matches = 0
    for section in payload["sections"]:
        for question in section["questions"]:
            if question["question_id"] == old_question_id:
                question["question_id"] = new_question_id
                matches += 1
    if matches != 1:
        raise PaperTaskReplacementError(
            "question to replace must occur exactly once in the paper"
        )
    return PaperAssemblyResult.model_validate(payload)


async def _validate_replacement(
    session: AsyncSession,
    review_graph: Any,
    job_id: str,
    assembly: PaperAssemblyResult,
    request: PaperTaskReview,
) -> PaperAssemblyResult:
    old_id = request.replace_question_id
    new_id = request.replacement_question_id
    if old_id is None or new_id is None:
        raise PaperTaskReplacementError("replacement IDs are required")

    state = await get_teacher_review_state(review_graph, job_id)
    if state is None:
        raise PaperTaskNotReviewableError("teacher review checkpoint is missing")
    if new_id not in state.candidate_question_ids:
        raise PaperTaskReplacementError(
            "replacement question does not satisfy the paper blueprint"
        )
    if new_id in state.selected_question_ids:
        raise PaperTaskReplacementError("replacement question is already selected")

    old_question = next(
        (
            question
            for section in assembly.sections
            for question in section.questions
            if question.question_id == old_id
        ),
        None,
    )
    new_question = await session.get(QuestionModel, new_id)
    if old_question is None or new_question is None:
        raise PaperTaskReplacementError("old or replacement question was not found")
    if (
        new_question.question_type != old_question.question_type.value
        or new_question.difficulty != old_question.difficulty.value
    ):
        raise PaperTaskReplacementError(
            "replacement must preserve question type and difficulty"
        )
    return _replace_assembly_question(
        assembly,
        old_question_id=old_id,
        new_question_id=new_id,
    )


async def review_paper_task(
    session: AsyncSession,
    review_graph: Any,
    job_id: str,
    request: PaperTaskReview,
) -> PaperTaskResponse:
    job = await session.get(PaperJobModel, job_id)
    if job is None or job.assembly_result is None:
        raise PaperTaskNotFoundError(job_id)
    if (
        job.status != PaperJobStatus.AWAITING_REVIEW.value
        or job.review_status != ReviewStatus.PENDING.value
    ):
        raise PaperTaskNotReviewableError(job.status)

    assembly = PaperAssemblyResult.model_validate(job.assembly_result)
    replacement_assembly = None
    if request.action == TeacherReviewAction.REPLACE:
        replacement_assembly = await _validate_replacement(
            session,
            review_graph,
            job_id,
            assembly,
            request,
        )

    state = await submit_teacher_review(review_graph, job_id, request)
    now = utc_now()
    if request.action == TeacherReviewAction.APPROVE:
        review_result = ReviewResult(
            status=ReviewStatus.APPROVED,
            reviewer=request.reviewer,
            comments=request.comment,
            reviewed_at=now,
        )
        job.status = PaperJobStatus.COMPLETED.value
        job.review_status = ReviewStatus.APPROVED.value
        job.review_result = review_result.model_dump(mode="json")
    elif request.action == TeacherReviewAction.REJECT:
        review_result = ReviewResult(
            status=ReviewStatus.REJECTED,
            reviewer=request.reviewer,
            comments=request.comment,
            issues=["TEACHER_REJECTED"],
            reviewed_at=now,
        )
        job.status = PaperJobStatus.FAILED.value
        job.failure_reason = request.comment
        job.review_status = ReviewStatus.REJECTED.value
        job.review_result = review_result.model_dump(mode="json")
    else:
        if replacement_assembly is None:
            raise RuntimeError("replacement assembly was not prepared")
        association = await session.get(
            PaperJobQuestionModel,
            {
                "job_id": job_id,
                "question_id": request.replace_question_id,
            },
        )
        if association is None:
            raise PaperTaskReplacementError("paper question relation was not found")
        association.question_id = request.replacement_question_id
        job.assembly_result = replacement_assembly.model_dump(mode="json")

    if job.status != state.execution.status.value:
        raise RuntimeError("business job and review checkpoint statuses diverged")
    job.updated_at = now
    await session.commit()
    await session.refresh(job)
    return task_response(job)

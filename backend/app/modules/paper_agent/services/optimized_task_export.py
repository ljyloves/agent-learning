"""Approved optimized-paper exports addressed by persisted job ID."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal
from zipfile import ZIP_DEFLATED, ZipFile

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PaperJobModel, PaperJobQuestionModel
from app.modules.paper_agent.schemas.assembly import (
    AssembledQuestion,
    AssembledSection,
    PaperAssemblyResult,
)
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus, ReviewStatus
from app.modules.paper_agent.schemas.question import QuestionDifficulty
from app.modules.paper_agent.schemas.student_paper import (
    AnswerSheetWordRequest,
    StudentPaperWordRequest,
    TeacherAnswerWordRequest,
)
from app.modules.paper_agent.services.document_conversion import (
    PDF_MIME_TYPE,
    PaperPdfFile,
    convert_word_export_to_pdf,
)
from app.modules.paper_agent.services.optimized_task import (
    OptimizedTaskNotFoundError,
)
from app.modules.paper_agent.services.paper_companions import (
    export_answer_sheet_word,
    export_teacher_answer_word,
)
from app.modules.paper_agent.services.student_paper import (
    DOCX_MIME_TYPE,
    StudentPaperWordFile,
    export_student_paper_word,
    safe_docx_filename,
)


OptimizedExportDocument = Literal["student", "teacher-answer", "answer-sheet"]
OptimizedExportFormat = Literal["docx", "pdf"]
ZIP_MIME_TYPE = "application/zip"


class OptimizedTaskNotApprovedError(RuntimeError):
    pass


class OptimizedTaskExportDataError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OptimizedTaskExportRequests:
    student: StudentPaperWordRequest
    teacher_answer: TeacherAnswerWordRequest
    answer_sheet: AnswerSheetWordRequest


@dataclass(frozen=True, slots=True)
class OptimizedTaskExportPackage:
    content: bytes
    filename: str
    entries: tuple[str, ...]


def _difficulty(level: int) -> QuestionDifficulty:
    if level <= 2:
        return QuestionDifficulty.EASY
    if level == 3:
        return QuestionDifficulty.MEDIUM
    return QuestionDifficulty.HARD


def _assembly_result(paper: dict) -> PaperAssemblyResult:
    try:
        sections = [
            AssembledSection(
                section_index=section["section_index"],
                question_type=section["question_type"],
                difficulty=_difficulty(section["difficulty_level"]),
                count=section["count"],
                score_per_question=section["score_per_question"],
                questions=[
                    AssembledQuestion(
                        question_id=question["question_id"],
                        question_type=question["question_type"],
                        difficulty=_difficulty(question["difficulty_level"]),
                        score=question["score"],
                    )
                    for question in section["questions"]
                ],
            )
            for section in paper["sections"]
        ]
        return PaperAssemblyResult(
            module_code=paper["module_code"],
            question_count=paper["question_count"],
            total_score=paper["total_score"],
            sections=sections,
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise OptimizedTaskExportDataError(
            "approved paper snapshot cannot be converted for export"
        ) from exc


def _paper_info(job: PaperJobModel) -> tuple[str, str, str, int]:
    payload = job.assembly_request or {}
    info = payload.get("paper_info", {}) if "optimization" in payload else {}
    return (
        info.get("paper_name") or "未命名高中生物试卷",
        info.get("grade") or "高中",
        info.get("exam_type") or "练习",
        info.get("duration_minutes") or 90,
    )


def _title(value: str, suffix: str = "") -> str:
    return f"{value[: 200 - len(suffix)]}{suffix}"


def _filename(value: str, suffix: str) -> str:
    return f"{value[: 119 - len(suffix)]}{suffix}"


async def _build_optimized_task_export_requests(
    session: AsyncSession,
    job_id: str,
    *,
    require_approved: bool,
) -> OptimizedTaskExportRequests:
    job = await session.get(PaperJobModel, job_id)
    if job is None or job.generation_mode != "optimized":
        raise OptimizedTaskNotFoundError(job_id)
    if require_approved and (
        job.status != PaperJobStatus.COMPLETED.value
        or job.review_status != ReviewStatus.APPROVED.value
        or job.review_result is None
    ):
        raise OptimizedTaskNotApprovedError(
            "paper must be approved before documents can be exported"
        )
    if not isinstance(job.assembly_result, dict):
        raise OptimizedTaskExportDataError("approved paper snapshot is missing")

    paper = _assembly_result(job.assembly_result)
    snapshot_ids = [
        question.question_id
        for section in paper.sections
        for question in section.questions
    ]
    persisted_ids = list(
        await session.scalars(
            select(PaperJobQuestionModel.question_id)
            .where(PaperJobQuestionModel.job_id == job_id)
            .order_by(PaperJobQuestionModel.position)
        )
    )
    if snapshot_ids != persisted_ids:
        raise OptimizedTaskExportDataError(
            "approved paper questions do not match the persisted review snapshot"
        )

    paper_name, grade, exam_type, duration_minutes = _paper_info(job)
    subtitle = f"{grade} · {exam_type}"
    return OptimizedTaskExportRequests(
        student=StudentPaperWordRequest(
            paper=paper,
            title=_title(paper_name),
            subtitle=subtitle,
            grade_name=grade,
            duration_minutes=duration_minutes,
            filename=_filename(paper_name, "_学生卷"),
        ),
        teacher_answer=TeacherAnswerWordRequest(
            paper=paper,
            title=_title(paper_name, "答案与解析"),
            subtitle=subtitle,
            filename=_filename(paper_name, "_教师答案解析"),
        ),
        answer_sheet=AnswerSheetWordRequest(
            paper=paper,
            title=_title(paper_name, "答题卡"),
            subtitle=subtitle,
            grade_name=grade,
            filename=_filename(paper_name, "_答题卡"),
        ),
    )


async def build_optimized_task_export_requests(
    session: AsyncSession,
    job_id: str,
) -> OptimizedTaskExportRequests:
    return await _build_optimized_task_export_requests(
        session,
        job_id,
        require_approved=True,
    )


async def _word_exports(
    session: AsyncSession,
    requests: OptimizedTaskExportRequests,
    *,
    storage_root: Path,
    template_root: Path,
) -> dict[OptimizedExportDocument, StudentPaperWordFile]:
    return {
        "student": await export_student_paper_word(
            session,
            requests.student,
            storage_root=storage_root,
            template_root=template_root,
        ),
        "teacher-answer": await export_teacher_answer_word(
            session,
            requests.teacher_answer,
            storage_root=storage_root,
            template_root=template_root,
        ),
        "answer-sheet": await export_answer_sheet_word(
            session,
            requests.answer_sheet,
            template_root=template_root,
        ),
    }


async def validate_optimized_task_export_readiness(
    session: AsyncSession,
    job_id: str,
    *,
    storage_root: Path,
    template_root: Path,
) -> None:
    requests = await _build_optimized_task_export_requests(
        session,
        job_id,
        require_approved=False,
    )
    words = await _word_exports(
        session,
        requests,
        storage_root=storage_root,
        template_root=template_root,
    )
    await asyncio.gather(
        *(convert_word_export_to_pdf(word) for word in words.values())
    )


async def export_optimized_task_file(
    session: AsyncSession,
    job_id: str,
    document: OptimizedExportDocument,
    file_format: OptimizedExportFormat,
    *,
    storage_root: Path,
    template_root: Path,
) -> StudentPaperWordFile | PaperPdfFile:
    requests = await build_optimized_task_export_requests(session, job_id)
    request_by_document = {
        "student": requests.student,
        "teacher-answer": requests.teacher_answer,
        "answer-sheet": requests.answer_sheet,
    }
    request = request_by_document[document]
    if document == "student":
        word = await export_student_paper_word(
            session,
            request,
            storage_root=storage_root,
            template_root=template_root,
        )
    elif document == "teacher-answer":
        word = await export_teacher_answer_word(
            session,
            request,
            storage_root=storage_root,
            template_root=template_root,
        )
    else:
        word = await export_answer_sheet_word(
            session,
            request,
            template_root=template_root,
        )
    return word if file_format == "docx" else await convert_word_export_to_pdf(word)


async def export_optimized_task_package(
    session: AsyncSession,
    job_id: str,
    *,
    storage_root: Path,
    template_root: Path,
) -> OptimizedTaskExportPackage:
    requests = await build_optimized_task_export_requests(session, job_id)
    words = await _word_exports(
        session,
        requests,
        storage_root=storage_root,
        template_root=template_root,
    )
    pdfs = await asyncio.gather(
        *(convert_word_export_to_pdf(words[key]) for key in words)
    )
    exported = [*words.values(), *pdfs]
    archive = BytesIO()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for item in exported:
            bundle.writestr(item.filename, item.content)
    entries = tuple(item.filename for item in exported)
    return OptimizedTaskExportPackage(
        content=archive.getvalue(),
        filename=(
            f"{Path(safe_docx_filename(requests.student.title, 'paper')).stem}"
            "_整套试卷.zip"
        ),
        entries=entries,
    )


__all__ = [
    "DOCX_MIME_TYPE",
    "PDF_MIME_TYPE",
    "ZIP_MIME_TYPE",
    "OptimizedExportDocument",
    "OptimizedExportFormat",
    "OptimizedTaskExportDataError",
    "OptimizedTaskExportPackage",
    "OptimizedTaskExportRequests",
    "OptimizedTaskNotApprovedError",
    "build_optimized_task_export_requests",
    "export_optimized_task_file",
    "export_optimized_task_package",
    "validate_optimized_task_export_readiness",
]

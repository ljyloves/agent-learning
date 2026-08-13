import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import (
    PaperJobModel,
    PaperJobQuestionModel,
    QuestionModel,
    QuestionSourceModel,
)
from app.modules.paper_agent.services.optimized_task_export import (
    OptimizedTaskExportDataError,
    OptimizedTaskNotApprovedError,
    build_optimized_task_export_requests,
    validate_optimized_task_export_readiness,
)


class OptimizedTaskExportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.job_ids = ["bio042-export-pending", "bio042-export-approved"]
        self.question_ids = ["bio042-export-q1", "bio042-export-q2"]
        self.source_id = "bio042-export-source"
        now = datetime.now(timezone.utc)
        paper = {
            "module_code": "BIO-M1",
            "question_count": 2,
            "total_score": 8,
            "sections": [
                {
                    "section_index": 0,
                    "question_type": "single_choice",
                    "difficulty_level": 2,
                    "count": 2,
                    "score_per_question": 4,
                    "questions": [
                        {
                            "question_id": question_id,
                            "question_type": "single_choice",
                            "difficulty_level": 2,
                            "score": 4,
                        }
                        for question_id in self.question_ids
                    ],
                }
            ],
            "audit": {
                "satisfied": True,
                "coverage_rate": 1.0,
                "distinct_knowledge_point_count": 2,
                "distinct_core_competency_count": 2,
                "distinct_source_count": 1,
            },
        }
        request = {
            "optimization": {"module_code": "BIO-M1"},
            "paper_info": {
                "paper_name": "BIO-042 导出验收试卷",
                "grade": "高一",
                "exam_type": "单元测试",
                "duration_minutes": 60,
            },
        }
        async with self.sessions() as session:
            session.add(
                QuestionSourceModel(
                    source_id=self.source_id,
                    source_type="manual",
                    name="BIO-042 export source",
                    external_id=self.source_id,
                )
            )
            await session.flush()
            session.add_all(
                [
                    QuestionModel(
                        id=question_id,
                        source_id=self.source_id,
                        question_type="single_choice",
                        difficulty="easy",
                        stem=f"{question_id} 题干",
                        answer="A",
                    )
                    for question_id in self.question_ids
                ]
            )
            await session.flush()
            session.add_all(
                [
                    PaperJobModel(
                        job_id=self.job_ids[0],
                        generation_mode="optimized",
                        status="awaiting_review",
                        review_status="pending",
                        assembly_request=request,
                        assembly_result=paper,
                        created_at=now,
                        updated_at=now,
                    ),
                    PaperJobModel(
                        job_id=self.job_ids[1],
                        generation_mode="optimized",
                        status="completed",
                        review_status="approved",
                        review_result={
                            "decision": "approved",
                            "reviewer": "teacher",
                            "comment": None,
                            "reviewed_at": now.isoformat(),
                        },
                        assembly_request=request,
                        assembly_result=paper,
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            await session.flush()
            for job_id in self.job_ids:
                session.add_all(
                    [
                        PaperJobQuestionModel(
                            job_id=job_id,
                            question_id=question_id,
                            position=position,
                        )
                        for position, question_id in enumerate(self.question_ids)
                    ]
                )
            await session.commit()

    async def asyncTearDown(self):
        async with self.sessions() as session:
            await session.execute(
                delete(PaperJobModel).where(PaperJobModel.job_id.in_(self.job_ids))
            )
            await session.execute(
                delete(QuestionModel).where(QuestionModel.id.in_(self.question_ids))
            )
            await session.execute(
                delete(QuestionSourceModel).where(
                    QuestionSourceModel.source_id == self.source_id
                )
            )
            await session.commit()
        await self.engine.dispose()

    async def test_pending_task_cannot_be_exported(self):
        async with self.sessions() as session:
            with self.assertRaises(OptimizedTaskNotApprovedError):
                await build_optimized_task_export_requests(session, self.job_ids[0])

    async def test_approved_task_builds_consistent_requests(self):
        async with self.sessions() as session:
            requests = await build_optimized_task_export_requests(
                session,
                self.job_ids[1],
            )

        self.assertEqual(requests.student.paper.question_count, 2)
        self.assertEqual(requests.student.duration_minutes, 60)
        self.assertEqual(requests.teacher_answer.paper, requests.student.paper)
        self.assertEqual(requests.answer_sheet.paper, requests.student.paper)
        self.assertIn("BIO-042", requests.student.filename)

    async def test_pending_review_can_be_preflighted_before_approval(self):
        fake_word = object()
        with (
            patch(
                "app.modules.paper_agent.services.optimized_task_export."
                "export_student_paper_word",
                new=AsyncMock(return_value=fake_word),
            ) as student,
            patch(
                "app.modules.paper_agent.services.optimized_task_export."
                "export_teacher_answer_word",
                new=AsyncMock(return_value=fake_word),
            ) as teacher,
            patch(
                "app.modules.paper_agent.services.optimized_task_export."
                "export_answer_sheet_word",
                new=AsyncMock(return_value=fake_word),
            ) as answer_sheet,
            patch(
                "app.modules.paper_agent.services.optimized_task_export."
                "convert_word_export_to_pdf",
                new=AsyncMock(return_value=object()),
            ) as convert_pdf,
        ):
            async with self.sessions() as session:
                await validate_optimized_task_export_readiness(
                    session,
                    self.job_ids[0],
                    storage_root=Path("/tmp/storage"),
                    template_root=Path("/tmp/templates"),
                )

        student.assert_awaited_once()
        teacher.assert_awaited_once()
        answer_sheet.assert_awaited_once()
        self.assertEqual(convert_pdf.await_count, 3)

    async def test_snapshot_order_mismatch_blocks_export(self):
        async with self.sessions() as session:
            job = await session.get(PaperJobModel, self.job_ids[1])
            snapshot = dict(job.assembly_result)
            sections = [dict(section) for section in snapshot["sections"]]
            sections[0]["questions"] = list(reversed(sections[0]["questions"]))
            snapshot["sections"] = sections
            job.assembly_result = snapshot
            await session.commit()
            with self.assertRaises(OptimizedTaskExportDataError):
                await build_optimized_task_export_requests(session, self.job_ids[1])


if __name__ == "__main__":
    unittest.main()

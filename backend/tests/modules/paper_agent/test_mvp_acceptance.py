import unittest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import PaperJobModel
from app.modules.paper_agent.graph.checkpoint import (
    CHECKPOINT_ALLOWED_MSGPACK_MODULES,
)
from app.modules.paper_agent.graph.workflow import build_teacher_review_graph
from app.modules.paper_agent.schemas.assembly import PaperAssemblyResult
from app.modules.paper_agent.schemas.optimized_task import (
    OptimizedPaperTaskCreate,
    OptimizedPaperTaskReview,
)
from app.modules.paper_agent.schemas.student_paper import (
    AnswerSheetWordRequest,
    StudentPaperWordRequest,
    TeacherAnswerWordRequest,
)
from app.modules.paper_agent.services.document_conversion import (
    convert_word_export_to_pdf,
)
from app.modules.paper_agent.services.mvp_acceptance import (
    BIO036_REVIEWER,
    bio036_optimization_payload,
    optimized_paper_to_assembly,
    prepare_bio036_candidates,
)
from app.modules.paper_agent.services.optimized_task import (
    create_optimized_task,
    review_optimized_task,
)
from app.modules.paper_agent.services.paper_companions import (
    export_answer_sheet_word,
    export_teacher_answer_word,
)
from app.modules.paper_agent.services.student_paper import export_student_paper_word


async def deterministic_embed(texts: list[str]) -> list[list[float]]:
    return [
        [1.0 if row == column else 0.0 for column in range(len(texts))]
        for row in range(len(texts))
    ]


class Bio036MvpAcceptanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        checkpointer = InMemorySaver(
            serde=JsonPlusSerializer(
                allowed_msgpack_modules=CHECKPOINT_ALLOWED_MSGPACK_MODULES,
            )
        )
        self.review_graph = build_teacher_review_graph(checkpointer)
        self.job_ids: list[str] = []

    async def asyncTearDown(self):
        async with self.sessions() as session:
            await session.execute(
                delete(PaperJobModel).where(PaperJobModel.job_id.in_(self.job_ids))
            )
            await session.commit()
        await self.engine.dispose()

    async def test_full_chain_optimizes_approves_and_exports_six_documents(self):
        async with self.sessions() as session:
            candidates = await prepare_bio036_candidates(session)
            created = await create_optimized_task(
                session,
                self.review_graph,
                OptimizedPaperTaskCreate.model_validate(
                    bio036_optimization_payload(candidates)
                ),
                embedder=deterministic_embed,
            )
            self.job_ids.append(created.job_id)
            self.assertEqual(created.status.value, "awaiting_review")
            self.assertTrue(created.awaiting_teacher)
            self.assertEqual(created.paper.question_count, 10)
            self.assertEqual(created.paper.total_score, 50)
            self.assertEqual(created.paper.audit.coverage_rate, 1.0)
            self.assertEqual(created.paper.audit.quality_approved_count, 10)
            self.assertEqual(created.paper.audit.selected_duplicate_pair_count, 0)

            approved = await review_optimized_task(
                session,
                self.review_graph,
                created.job_id,
                OptimizedPaperTaskReview(
                    action="approve",
                    reviewer=BIO036_REVIEWER,
                    comment="BIO-036 automated teacher acceptance.",
                ),
            )
            self.assertEqual(approved.status.value, "completed")
            self.assertEqual(approved.review_status.value, "approved")
            self.assertFalse(approved.awaiting_teacher)

            assembly = PaperAssemblyResult.model_validate(
                optimized_paper_to_assembly(
                    approved.paper.model_dump(mode="json")
                )
            )
            student = await export_student_paper_word(
                session,
                StudentPaperWordRequest(paper=assembly),
                storage_root=settings.paper_agent_storage_path,
                template_root=settings.paper_agent_template_path,
            )
            teacher = await export_teacher_answer_word(
                session,
                TeacherAnswerWordRequest(paper=assembly),
                storage_root=settings.paper_agent_storage_path,
                template_root=settings.paper_agent_template_path,
            )
            answer_sheet = await export_answer_sheet_word(
                session,
                AnswerSheetWordRequest(paper=assembly),
                template_root=settings.paper_agent_template_path,
            )

        for label, exported in (
            ("student", student),
            ("teacher", teacher),
            ("answer_sheet", answer_sheet),
        ):
            self.assertTrue(exported.content.startswith(b"PK"))
            try:
                pdf = await convert_word_export_to_pdf(exported)
            except Exception as exc:
                self.fail(f"{label} PDF conversion failed: {exc}")
            self.assertTrue(pdf.content.startswith(b"%PDF-"))
            self.assertTrue(pdf.inspection.passed)
            self.assertEqual(pdf.inspection.blank_pages, ())
            self.assertEqual(pdf.inspection.abnormal_break_pages, ())
        self.assertFalse(student.allow_answers)
        self.assertTrue(teacher.allow_answers)
        self.assertFalse(answer_sheet.allow_answers)


if __name__ == "__main__":
    unittest.main()

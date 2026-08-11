import unittest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import PaperJobModel, PaperJobQuestionModel, QuestionModel
from app.modules.paper_agent.graph.checkpoint import (
    CHECKPOINT_ALLOWED_MSGPACK_MODULES,
)
from app.modules.paper_agent.graph.workflow import build_teacher_review_graph
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus, ReviewStatus
from app.modules.paper_agent.schemas.task import PaperTaskCreate, PaperTaskReview
from app.modules.paper_agent.services.checkpoint import get_teacher_review_state
from app.modules.paper_agent.services.task import (
    create_paper_task,
    get_paper_task,
    review_paper_task,
)


def task_request() -> PaperTaskCreate:
    return PaperTaskCreate(
        assembly={
            "module_code": "BIO-M1",
            "question_count": 7,
            "total_score": 26,
            "sections": [
                {
                    "question_type": "single_choice",
                    "difficulty": "easy",
                    "count": 3,
                    "score_per_question": 4,
                },
                {
                    "question_type": "true_false",
                    "difficulty": "medium",
                    "count": 2,
                    "score_per_question": 2,
                },
                {
                    "question_type": "fill_blank",
                    "difficulty": "hard",
                    "count": 2,
                    "score_per_question": 5,
                },
            ],
            "random_seed": 19,
        }
    )


class PaperTaskServiceTests(unittest.IsolatedAsyncioTestCase):
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
            for job_id in self.job_ids:
                job = await session.get(PaperJobModel, job_id)
                if job is not None:
                    await session.delete(job)
            await session.commit()
        await self.engine.dispose()

    async def create_task(self, session):
        task = await create_paper_task(session, self.review_graph, task_request())
        self.job_ids.append(task.job_id)
        return task

    async def test_create_query_and_approve_complete_the_task(self):
        async with self.sessions() as session:
            created = await self.create_task(session)
            fetched = await get_paper_task(session, created.job_id)
            relation_count = await session.scalar(
                select(func.count())
                .select_from(PaperJobQuestionModel)
                .where(PaperJobQuestionModel.job_id == created.job_id)
            )

            self.assertEqual(created.status, PaperJobStatus.AWAITING_REVIEW)
            self.assertEqual(created.review_status, ReviewStatus.PENDING)
            self.assertTrue(created.awaiting_teacher)
            self.assertEqual(created.assembly.question_count, 7)
            self.assertEqual(created.assembly.total_score, 26)
            self.assertEqual(fetched, created)
            self.assertEqual(relation_count, 7)

            completed = await review_paper_task(
                session,
                self.review_graph,
                created.job_id,
                PaperTaskReview(
                    action="approve",
                    reviewer="teacher-m2",
                    comment="M2 paper approved.",
                ),
            )
            persisted = await session.get(PaperJobModel, created.job_id)

        self.assertEqual(completed.status, PaperJobStatus.COMPLETED)
        self.assertEqual(completed.review_status, ReviewStatus.APPROVED)
        self.assertEqual(completed.review_result.reviewer, "teacher-m2")
        self.assertFalse(completed.awaiting_teacher)
        self.assertEqual(persisted.review_result["reviewer"], "teacher-m2")

    async def test_reject_updates_business_failure_and_review_result(self):
        async with self.sessions() as session:
            created = await self.create_task(session)
            rejected = await review_paper_task(
                session,
                self.review_graph,
                created.job_id,
                PaperTaskReview(
                    action="reject",
                    reviewer="teacher-reject",
                    comment="Knowledge coverage is not suitable.",
                ),
            )
            persisted = await session.get(PaperJobModel, created.job_id)

        self.assertEqual(rejected.status, PaperJobStatus.FAILED)
        self.assertEqual(rejected.review_status, ReviewStatus.REJECTED)
        self.assertEqual(rejected.review_result.reviewer, "teacher-reject")
        self.assertEqual(
            rejected.failure_reason,
            "Knowledge coverage is not suitable.",
        )
        self.assertEqual(persisted.review_result["issues"], ["TEACHER_REJECTED"])

    async def test_replace_preserves_blueprint_and_relations_then_can_approve(self):
        async with self.sessions() as session:
            created = await self.create_task(session)
            old_question = created.assembly.sections[0].questions[0]
            state = await get_teacher_review_state(
                self.review_graph,
                created.job_id,
            )
            replacement_id = await session.scalar(
                select(QuestionModel.id)
                .where(
                    QuestionModel.id.in_(state.candidate_question_ids),
                    QuestionModel.id.not_in(state.selected_question_ids),
                    QuestionModel.question_type
                    == old_question.question_type.value,
                    QuestionModel.difficulty == old_question.difficulty.value,
                )
                .order_by(QuestionModel.id)
                .limit(1)
            )
            self.assertIsNotNone(replacement_id)

            replaced = await review_paper_task(
                session,
                self.review_graph,
                created.job_id,
                PaperTaskReview(
                    action="replace",
                    reviewer="teacher-replace",
                    comment="Replace this item.",
                    replace_question_id=old_question.question_id,
                    replacement_question_id=replacement_id,
                ),
            )
            relation_ids = set(
                await session.scalars(
                    select(PaperJobQuestionModel.question_id).where(
                        PaperJobQuestionModel.job_id == created.job_id
                    )
                )
            )

            self.assertEqual(replaced.status, PaperJobStatus.AWAITING_REVIEW)
            self.assertEqual(replaced.assembly.question_count, 7)
            self.assertEqual(replaced.assembly.total_score, 26)
            self.assertNotIn(old_question.question_id, relation_ids)
            self.assertIn(replacement_id, relation_ids)

            completed = await review_paper_task(
                session,
                self.review_graph,
                created.job_id,
                PaperTaskReview(action="approve", reviewer="teacher-replace"),
            )

        self.assertEqual(completed.status, PaperJobStatus.COMPLETED)
        self.assertEqual(completed.assembly.question_count, 7)
        self.assertEqual(completed.assembly.total_score, 26)


if __name__ == "__main__":
    unittest.main()

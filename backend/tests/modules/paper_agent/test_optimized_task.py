import unittest
from datetime import datetime, timedelta, timezone

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import (
    PaperJobModel,
    PaperJobQuestionModel,
    QuestionAnalysisModel,
    QuestionCoreCompetencyModel,
    QuestionKnowledgePointModel,
    QuestionModel,
    QuestionSourceModel,
)
from app.modules.paper_agent.graph.checkpoint import (
    CHECKPOINT_ALLOWED_MSGPACK_MODULES,
)
from app.modules.paper_agent.graph.workflow import build_teacher_review_graph
from app.modules.paper_agent.schemas.optimization import (
    CoverageConstraint,
    DifficultyQuota,
    DiversityConstraint,
    KnowledgePointTarget,
    OptimizedPaperRequest,
)
from app.modules.paper_agent.schemas.optimized_task import (
    OptimizedPaperLockUpdate,
    OptimizedPaperInfo,
    OptimizedPaperReassemble,
    OptimizedPaperReplace,
    OptimizedPaperTaskCreate,
    OptimizedPaperTaskReview,
)
from app.modules.paper_agent.schemas.paper_job import (
    PaperJobStatus,
    ReviewStatus,
)
from app.modules.paper_agent.schemas.question import QuestionType
from app.modules.paper_agent.services.checkpoint import get_teacher_review_state
from app.modules.paper_agent.services.optimization import NoFeasiblePaperError
from app.modules.paper_agent.services.optimized_task import (
    LockedQuestionError,
    create_optimized_task,
    get_optimized_task,
    list_optimized_tasks,
    reassemble_optimized_task,
    replace_optimized_question,
    review_optimized_task,
    update_optimized_task_locks,
)


QUESTION_SPECS = [
    ("bio030-k01-a", "bio030-source-a", "BIO-M1-K01", "BIO-C1"),
    ("bio030-k01-b", "bio030-source-b", "BIO-M1-K01", "BIO-C1"),
    ("bio030-k01-c", "bio030-source-c", "BIO-M1-K01", "BIO-C1"),
    ("bio030-k02-a", "bio030-source-d", "BIO-M1-K02", "BIO-C2"),
    ("bio030-k02-b", "bio030-source-e", "BIO-M1-K02", "BIO-C2"),
    ("bio030-k02-c", "bio030-source-f", "BIO-M1-K02", "BIO-C2"),
]


async def deterministic_embed(texts: list[str]) -> list[list[float]]:
    return [
        [1.0 if row == column else 0.0 for column in range(len(texts))]
        for row in range(len(texts))
    ]


def optimization_request(
    *,
    exclude_question_ids: list[str] | None = None,
) -> OptimizedPaperRequest:
    return OptimizedPaperRequest(
        module_code="BIO-M1",
        question_count=2,
        total_score=8,
        difficulty_quotas=[
            DifficultyQuota(
                question_type=QuestionType.SINGLE_CHOICE,
                difficulty_level=2,
                count=2,
                score_per_question=4,
            )
        ],
        coverage=CoverageConstraint(
            targets=[
                KnowledgePointTarget(code="BIO-M1-K01"),
                KnowledgePointTarget(code="BIO-M1-K02"),
            ],
            minimum_coverage_rate=1.0,
        ),
        diversity=DiversityConstraint(
            minimum_distinct_knowledge_points=2,
            minimum_distinct_core_competencies=2,
            minimum_distinct_sources=2,
            maximum_questions_per_knowledge_point=1,
            maximum_questions_per_source=1,
            semantic_similarity_threshold=0.94,
        ),
        exclude_question_ids=exclude_question_ids or [],
        random_seed=30,
    )


def selected_ids(task) -> list[str]:
    return [
        question.question_id
        for section in task.paper.sections
        for question in section.questions
    ]


class OptimizedPaperTaskTests(unittest.IsolatedAsyncioTestCase):
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
        now = datetime.now(timezone.utc)
        async with self.sessions() as session:
            self.preexisting_question_ids = list(
                (await session.scalars(select(QuestionModel.id))).all()
            )
            session.add_all(
                [
                    QuestionSourceModel(
                        source_id=source_id,
                        source_type="manual",
                        name=source_id,
                        external_id=source_id,
                    )
                    for _, source_id, _, _ in QUESTION_SPECS
                ]
            )
            await session.flush()
            for question_id, source_id, knowledge_code, competency_code in QUESTION_SPECS:
                session.add(
                    QuestionModel(
                        id=question_id,
                        source_id=source_id,
                        question_type="single_choice",
                        difficulty="medium",
                        stem=f"{question_id} 的独立测试题干。",
                        answer="A",
                    )
                )
                await session.flush()
                session.add_all(
                    [
                        QuestionKnowledgePointModel(
                            question_id=question_id,
                            knowledge_point_code=knowledge_code,
                        ),
                        QuestionCoreCompetencyModel(
                            question_id=question_id,
                            competency_code=competency_code,
                        ),
                        QuestionAnalysisModel(
                            analysis_id=f"{question_id}-difficulty",
                            question_id=question_id,
                            analysis_type="difficulty_estimation",
                            model="test-model",
                            result={
                                "difficulty_level": 2,
                                "estimated_correct_rate": 0.72,
                                "confidence": 0.9,
                                "rationale": "BIO-030 test difficulty.",
                            },
                            created_at=now,
                        ),
                        QuestionAnalysisModel(
                            analysis_id=f"{question_id}-quality",
                            question_id=question_id,
                            analysis_type="quality_review",
                            model="test-model",
                            result={
                                "issues": [],
                                "summary": "BIO-030 test quality review.",
                                "passed": True,
                            },
                            created_at=now,
                        ),
                    ]
                )
            await session.commit()

    async def asyncTearDown(self):
        question_ids = [spec[0] for spec in QUESTION_SPECS]
        source_ids = [spec[1] for spec in QUESTION_SPECS]
        async with self.sessions() as session:
            await session.execute(
                delete(PaperJobModel).where(PaperJobModel.job_id.in_(self.job_ids))
            )
            await session.execute(
                delete(QuestionModel).where(QuestionModel.id.in_(question_ids))
            )
            await session.execute(
                delete(QuestionSourceModel).where(
                    QuestionSourceModel.source_id.in_(source_ids)
                )
            )
            await session.commit()
        await self.engine.dispose()

    async def create_task(self, session, *, paper_info=None):
        task = await create_optimized_task(
            session,
            self.review_graph,
            OptimizedPaperTaskCreate(
                optimization=optimization_request(
                    exclude_question_ids=self.preexisting_question_ids,
                ),
                paper_info=paper_info,
            ),
            embedder=deterministic_embed,
        )
        self.job_ids.append(task.job_id)
        return task

    async def test_list_filters_paginates_and_orders_by_updated_at(self):
        async with self.sessions() as session:
            first = await self.create_task(
                session,
                paper_info=OptimizedPaperInfo(
                    paper_name="细胞结构月考试卷",
                    grade="高一",
                    exam_type="月考",
                    duration_minutes=60,
                ),
            )
            second = await self.create_task(
                session,
                paper_info=OptimizedPaperInfo(
                    paper_name="分子与细胞单元测试",
                    grade="高一",
                    exam_type="单元测试",
                    duration_minutes=45,
                ),
            )
            now = datetime.now(timezone.utc)
            first_job = await session.get(PaperJobModel, first.job_id)
            second_job = await session.get(PaperJobModel, second.job_id)
            first_job.updated_at = now - timedelta(minutes=1)
            second_job.updated_at = now
            await session.commit()

            page_one = await list_optimized_tasks(
                session,
                page=1,
                page_size=1,
            )
            page_two = await list_optimized_tasks(
                session,
                page=2,
                page_size=1,
            )
            by_name = await list_optimized_tasks(
                session,
                keyword="细胞结构",
            )
            by_id = await list_optimized_tasks(
                session,
                keyword=second.job_id,
            )
            pending = await list_optimized_tasks(
                session,
                status=PaperJobStatus.AWAITING_REVIEW,
                review_status=ReviewStatus.PENDING,
            )

        self.assertGreaterEqual(page_one.total, 2)
        self.assertEqual(page_one.pages, page_one.total)
        self.assertEqual(page_one.items[0].job_id, second.job_id)
        self.assertEqual(page_two.items[0].job_id, first.job_id)
        self.assertEqual(by_name.total, 1)
        self.assertEqual(by_name.items[0].paper_name, "细胞结构月考试卷")
        self.assertEqual(by_id.total, 1)
        self.assertEqual(by_id.items[0].job_id, second.job_id)
        pending_ids = {item.job_id for item in pending.items}
        self.assertTrue({first.job_id, second.job_id}.issubset(pending_ids))
        self.assertEqual(page_one.items[0].question_count, 2)
        self.assertEqual(page_one.items[0].total_score, 8)
        self.assertTrue(page_one.items[0].awaiting_teacher)

    async def test_legacy_request_uses_defaults_and_remains_readable(self):
        async with self.sessions() as session:
            created = await self.create_task(session)
            job = await session.get(PaperJobModel, created.job_id)
            job.assembly_request = job.assembly_request["optimization"]
            await session.commit()

            listed = await list_optimized_tasks(
                session,
                keyword=created.job_id,
            )
            persisted = await get_optimized_task(session, created.job_id)

        self.assertEqual(listed.total, 1)
        item = listed.items[0]
        self.assertEqual(item.paper_name, "未命名高中生物试卷")
        self.assertEqual(item.grade, "高中")
        self.assertEqual(item.exam_type, "练习")
        self.assertEqual(item.duration_minutes, 90)
        self.assertEqual(persisted.job_id, created.job_id)

    async def test_reassemble_preserves_paper_info(self):
        paper_info = OptimizedPaperInfo(
            paper_name="BIO-038 元数据试卷",
            grade="高二",
            exam_type="期中考试",
            duration_minutes=75,
        )
        async with self.sessions() as session:
            created = await self.create_task(session, paper_info=paper_info)
            reassembled = await reassemble_optimized_task(
                session,
                self.review_graph,
                created.job_id,
                OptimizedPaperReassemble(
                    reviewer="teacher-metadata",
                    random_seed=31,
                ),
                embedder=deterministic_embed,
            )
            job = await session.get(PaperJobModel, created.job_id)
            listed = await list_optimized_tasks(
                session,
                keyword="BIO-038",
            )

        self.assertEqual(reassembled.job_id, created.job_id)
        self.assertEqual(
            job.assembly_request["paper_info"],
            paper_info.model_dump(),
        )
        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.items[0].duration_minutes, 75)

    async def test_locked_question_cannot_be_replaced(self):
        async with self.sessions() as session:
            created = await self.create_task(session)
            locked_id = selected_ids(created)[0]
            locked = await update_optimized_task_locks(
                session,
                created.job_id,
                OptimizedPaperLockUpdate(question_ids=[locked_id], locked=True),
            )
            with self.assertRaises(LockedQuestionError):
                await replace_optimized_question(
                    session,
                    self.review_graph,
                    created.job_id,
                    OptimizedPaperReplace(
                        question_id=locked_id,
                        reviewer="teacher-lock",
                    ),
                    embedder=deterministic_embed,
                )

            persisted_lock = await session.scalar(
                select(PaperJobQuestionModel.is_locked).where(
                    PaperJobQuestionModel.job_id == created.job_id,
                    PaperJobQuestionModel.question_id == locked_id,
                )
            )

        self.assertEqual(locked.locked_question_ids, [locked_id])
        self.assertTrue(persisted_lock)

    async def test_replace_preserves_locks_and_every_hard_constraint(self):
        async with self.sessions() as session:
            created = await self.create_task(session)
            locked_id, old_id = selected_ids(created)
            await update_optimized_task_locks(
                session,
                created.job_id,
                OptimizedPaperLockUpdate(question_ids=[locked_id], locked=True),
            )
            replaced = await replace_optimized_question(
                session,
                self.review_graph,
                created.job_id,
                OptimizedPaperReplace(
                    question_id=old_id,
                    reviewer="teacher-replace",
                    comment="Replace one unlocked question.",
                ),
                embedder=deterministic_embed,
            )
            state = await get_teacher_review_state(
                self.review_graph,
                created.job_id,
            )

        new_ids = selected_ids(replaced)
        self.assertIn(locked_id, new_ids)
        self.assertNotIn(old_id, new_ids)
        self.assertEqual(replaced.locked_question_ids, [locked_id])
        self.assertTrue(replaced.paper.audit.satisfied)
        self.assertEqual(replaced.paper.audit.coverage_rate, 1.0)
        self.assertEqual(set(state.selected_question_ids), set(new_ids))
        self.assertEqual(state.execution.replacement_count, 1)

    async def test_reassemble_replaces_only_unlocked_then_can_approve(self):
        async with self.sessions() as session:
            created = await self.create_task(session)
            locked_id, old_unlocked_id = selected_ids(created)
            await update_optimized_task_locks(
                session,
                created.job_id,
                OptimizedPaperLockUpdate(question_ids=[locked_id], locked=True),
            )
            reassembled = await reassemble_optimized_task(
                session,
                self.review_graph,
                created.job_id,
                OptimizedPaperReassemble(
                    reviewer="teacher-reassemble",
                    comment="Regenerate every unlocked slot.",
                ),
                embedder=deterministic_embed,
            )
            paused = await get_teacher_review_state(
                self.review_graph,
                created.job_id,
            )
            completed = await review_optimized_task(
                session,
                self.review_graph,
                created.job_id,
                OptimizedPaperTaskReview(
                    action="approve",
                    reviewer="teacher-approve",
                ),
            )

        new_ids = selected_ids(reassembled)
        self.assertIn(locked_id, new_ids)
        self.assertNotIn(old_unlocked_id, new_ids)
        self.assertEqual(reassembled.locked_question_ids, [locked_id])
        self.assertTrue(reassembled.paper.audit.satisfied)
        self.assertEqual(set(paused.selected_question_ids), set(new_ids))
        self.assertEqual(completed.status, PaperJobStatus.COMPLETED)
        self.assertFalse(completed.awaiting_teacher)

    async def test_reassemble_rejects_an_all_locked_paper(self):
        async with self.sessions() as session:
            created = await self.create_task(session)
            await update_optimized_task_locks(
                session,
                created.job_id,
                OptimizedPaperLockUpdate(
                    question_ids=selected_ids(created),
                    locked=True,
                ),
            )
            with self.assertRaises(LockedQuestionError):
                await reassemble_optimized_task(
                    session,
                    self.review_graph,
                    created.job_id,
                    OptimizedPaperReassemble(reviewer="teacher-all-locked"),
                    embedder=deterministic_embed,
                )

    async def test_infeasible_explicit_replacement_keeps_original_selection(self):
        async with self.sessions() as session:
            created = await self.create_task(session)
            original_ids = selected_ids(created)
            locked_id = next(
                question_id
                for question_id in original_ids
                if question_id.startswith("bio030-k01")
            )
            old_id = next(
                question_id
                for question_id in original_ids
                if question_id.startswith("bio030-k02")
            )
            incompatible_id = next(
                question_id
                for question_id, _, _, _ in QUESTION_SPECS
                if question_id.startswith("bio030-k01")
                and question_id not in original_ids
            )
            await update_optimized_task_locks(
                session,
                created.job_id,
                OptimizedPaperLockUpdate(question_ids=[locked_id], locked=True),
            )

            with self.assertRaises(NoFeasiblePaperError):
                await replace_optimized_question(
                    session,
                    self.review_graph,
                    created.job_id,
                    OptimizedPaperReplace(
                        question_id=old_id,
                        replacement_question_id=incompatible_id,
                        reviewer="teacher-infeasible",
                    ),
                    embedder=deterministic_embed,
                )

            persisted = await get_optimized_task(session, created.job_id)
            state = await get_teacher_review_state(
                self.review_graph,
                created.job_id,
            )

        self.assertEqual(selected_ids(persisted), original_ids)
        self.assertEqual(state.selected_question_ids, original_ids)


if __name__ == "__main__":
    unittest.main()

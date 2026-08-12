import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import (
    QuestionAnalysisModel,
    QuestionCoreCompetencyModel,
    QuestionKnowledgePointModel,
    QuestionModel,
    QuestionSourceModel,
)
from app.modules.paper_agent.schemas.optimization import (
    CoverageConstraint,
    DifficultyQuota,
    DiversityConstraint,
    KnowledgePointTarget,
    OptimizedPaperRequest,
)
from app.modules.paper_agent.schemas.question import QuestionType
from app.modules.paper_agent.services.optimization import (
    NoFeasiblePaperError,
    OptimizationEmbeddingError,
    optimize_paper,
)


QUESTION_SPECS = [
    (
        "bio029-q1",
        "bio029-source-a",
        "single_choice",
        "细胞膜主要由磷脂双分子层构成。",
        "BIO-M1-K01",
        "BIO-C1",
        2,
        True,
    ),
    (
        "bio029-q2",
        "bio029-source-b",
        "single_choice",
        "核糖体参与蛋白质的合成。",
        "BIO-M1-K02",
        "BIO-C2",
        2,
        True,
    ),
    (
        "bio029-q3",
        "bio029-source-a",
        "true_false",
        "分析膜运输图示，判断主动运输机制。",
        "BIO-M1-K03",
        "BIO-C3",
        4,
        True,
    ),
    (
        "bio029-q4",
        "bio029-source-b",
        "true_false",
        "酶的活性受到温度和酸碱度影响。",
        "BIO-M1-K04",
        "BIO-C4",
        4,
        True,
    ),
    (
        "bio029-q5",
        "bio029-source-a",
        "single_choice",
        "细胞膜主要由磷脂双分子层构成。",
        "BIO-M1-K02",
        "BIO-C2",
        2,
        True,
    ),
    (
        "bio029-q6",
        "bio029-source-b",
        "true_false",
        "分析膜运输示意图，判断主动运输的机制。",
        "BIO-M1-K04",
        "BIO-C4",
        4,
        True,
    ),
    (
        "bio029-qbad",
        "bio029-source-c",
        "single_choice",
        "缺少条件的歧义题。",
        "BIO-M1-K05",
        "BIO-C1",
        2,
        False,
    ),
]


async def deterministic_embed(texts: list[str]) -> list[list[float]]:
    vectors = []
    for index, text in enumerate(texts):
        vector = [0.0] * len(texts)
        if "主动运输" in text:
            vector[0] = 1.0
        else:
            vector[index] = 1.0
        vectors.append(vector)
    return vectors


def strict_request() -> OptimizedPaperRequest:
    return OptimizedPaperRequest(
        module_code="BIO-M1",
        question_count=4,
        total_score=18,
        difficulty_quotas=[
            DifficultyQuota(
                question_type=QuestionType.SINGLE_CHOICE,
                difficulty_level=2,
                count=2,
                score_per_question=4,
            ),
            DifficultyQuota(
                question_type=QuestionType.TRUE_FALSE,
                difficulty_level=4,
                count=2,
                score_per_question=5,
            ),
        ],
        coverage=CoverageConstraint(
            targets=[
                KnowledgePointTarget(code="BIO-M1-K01"),
                KnowledgePointTarget(code="BIO-M1-K02"),
                KnowledgePointTarget(code="BIO-M1-K03"),
                KnowledgePointTarget(code="BIO-M1-K04"),
            ],
            minimum_coverage_rate=1.0,
        ),
        diversity=DiversityConstraint(
            minimum_distinct_knowledge_points=4,
            minimum_distinct_core_competencies=4,
            minimum_distinct_sources=2,
            maximum_questions_per_knowledge_point=1,
            maximum_questions_per_source=2,
            semantic_similarity_threshold=0.94,
        ),
        random_seed=29,
    )


class PaperOptimizationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        now = datetime.now(timezone.utc)
        async with self.sessions() as session:
            session.add_all(
                [
                    QuestionSourceModel(
                        source_id=source_id,
                        source_type="manual",
                        name=source_id,
                        external_id=source_id,
                    )
                    for source_id in {
                        spec[1] for spec in QUESTION_SPECS
                    }
                ]
            )
            await session.flush()
            for (
                question_id,
                source_id,
                question_type,
                stem,
                knowledge_code,
                competency_code,
                difficulty_level,
                quality_passed,
            ) in QUESTION_SPECS:
                session.add(
                    QuestionModel(
                        id=question_id,
                        source_id=source_id,
                        question_type=question_type,
                        difficulty="medium",
                        stem=stem,
                        answer="测试答案",
                    )
                )
                await session.flush()
                session.add(
                    QuestionKnowledgePointModel(
                        question_id=question_id,
                        knowledge_point_code=knowledge_code,
                    )
                )
                session.add(
                    QuestionCoreCompetencyModel(
                        question_id=question_id,
                        competency_code=competency_code,
                    )
                )
                correct_rate = 0.75 if difficulty_level == 2 else 0.30
                session.add(
                    QuestionAnalysisModel(
                        analysis_id=f"{question_id}-difficulty",
                        question_id=question_id,
                        analysis_type="difficulty_estimation",
                        model="test-model",
                        result={
                            "difficulty_level": difficulty_level,
                            "estimated_correct_rate": correct_rate,
                            "confidence": 0.9,
                            "rationale": "测试难度分析。",
                        },
                        created_at=now,
                    )
                )
                issues = [] if quality_passed else [
                    {
                        "issue_type": "ambiguity",
                        "severity": "error",
                        "location": "stem",
                        "description": "条件不足。",
                        "suggestion": "补充条件。",
                        "confidence": 0.95,
                    }
                ]
                session.add(
                    QuestionAnalysisModel(
                        analysis_id=f"{question_id}-quality",
                        question_id=question_id,
                        analysis_type="quality_review",
                        model="test-model",
                        result={
                            "issues": issues,
                            "summary": "测试质量审核。",
                            "passed": quality_passed,
                        },
                        created_at=now,
                    )
                )
            session.add(
                QuestionAnalysisModel(
                    analysis_id="bio029-q1-quality-old",
                    question_id="bio029-q1",
                    analysis_type="quality_review",
                    model="test-model",
                    result={
                        "issues": [
                            {
                                "issue_type": "ambiguity",
                                "severity": "warning",
                                "location": "stem",
                                "description": "旧审核结果。",
                                "suggestion": "旧建议。",
                                "confidence": 0.6,
                            }
                        ],
                        "summary": "旧审核。",
                        "passed": False,
                    },
                    created_at=now - timedelta(days=1),
                )
            )
            await session.commit()

    async def asyncTearDown(self):
        question_ids = [spec[0] for spec in QUESTION_SPECS]
        source_ids = list({spec[1] for spec in QUESTION_SPECS})
        async with self.sessions() as session:
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

    async def test_satisfies_all_constraints_and_uses_latest_reviews(self):
        async with self.sessions() as session:
            result = await optimize_paper(
                session,
                strict_request(),
                embedder=deterministic_embed,
            )

        selected_ids = {
            question.question_id
            for section in result.sections
            for question in section.questions
        }
        self.assertEqual(selected_ids, {
            "bio029-q1",
            "bio029-q2",
            "bio029-q3",
            "bio029-q4",
        })
        self.assertEqual(result.audit.coverage_rate, 1.0)
        self.assertEqual(result.audit.distinct_knowledge_point_count, 4)
        self.assertEqual(result.audit.distinct_core_competency_count, 4)
        self.assertEqual(result.audit.distinct_source_count, 2)
        self.assertEqual(result.audit.quality_approved_count, 4)
        self.assertEqual(result.audit.selected_duplicate_pair_count, 0)
        self.assertNotIn("bio029-qbad", selected_ids)

    async def test_exact_and_semantic_duplicates_cannot_coexist(self):
        async with self.sessions() as session:
            result = await optimize_paper(
                session,
                strict_request(),
                embedder=deterministic_embed,
            )

        selected_ids = {
            question.question_id
            for section in result.sections
            for question in section.questions
        }
        self.assertFalse({"bio029-q1", "bio029-q5"} <= selected_ids)
        self.assertFalse({"bio029-q3", "bio029-q6"} <= selected_ids)

    async def test_reports_no_feasible_solution_without_relaxing_diversity(self):
        payload = strict_request().model_dump(mode="json")
        payload["diversity"]["minimum_distinct_sources"] = 3
        request = OptimizedPaperRequest.model_validate(payload)

        async with self.sessions() as session:
            with self.assertRaises(NoFeasiblePaperError) as context:
                await optimize_paper(
                    session,
                    request,
                    embedder=deterministic_embed,
                )

        self.assertGreaterEqual(context.exception.candidate_count, 4)
        self.assertIn("single_choice:2", context.exception.quota_availability)

    async def test_rejects_inconsistent_embedding_dimensions(self):
        async def invalid_embed(texts: list[str]) -> list[list[float]]:
            return [[1.0] * (index + 1) for index, _ in enumerate(texts)]

        async with self.sessions() as session:
            with self.assertRaises(OptimizationEmbeddingError):
                await optimize_paper(
                    session,
                    strict_request(),
                    embedder=invalid_embed,
                )


if __name__ == "__main__":
    unittest.main()

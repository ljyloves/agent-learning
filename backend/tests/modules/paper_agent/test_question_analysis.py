import json
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import BadRequestError
from pydantic import ValidationError
from sqlalchemy import delete, select
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
from app.modules.paper_agent.schemas.analysis import (
    DifficultyEstimationLLMOutput,
    QualityIssue,
    QualityIssueType,
    QualityReviewLLMOutput,
    QualitySeverity,
    QuestionAnalysisType,
)
from app.modules.paper_agent.schemas.question import (
    Question,
    QuestionOption,
    QuestionType,
)
from app.modules.paper_agent.schemas.source import QuestionSource, SourceType
from app.modules.paper_agent.services.persistence import QuestionPersistenceContext
from app.modules.paper_agent.services.question_analysis import (
    QuestionAnalysisOutputError,
    QuestionAnalysisPrerequisiteError,
    _complete_analysis,
    _difficulty_response_format,
    _merge_quality_issues,
    estimate_question_difficulty,
    review_question_quality,
)


class QuestionAnalysisSchemaTests(unittest.TestCase):
    def test_difficulty_level_and_correct_rate_must_be_consistent(self):
        with self.assertRaises(ValidationError):
            DifficultyEstimationLLMOutput(
                difficulty_level=5,
                estimated_correct_rate=0.9,
                confidence=0.8,
                rationale="难度和正确率矛盾。",
            )

    def test_quality_output_rejects_unknown_issue_type(self):
        with self.assertRaises(ValidationError):
            QualityReviewLLMOutput.model_validate(
                {
                    "issues": [
                        {
                            "issue_type": "style_problem",
                            "severity": "warning",
                            "location": "question",
                            "description": "不受支持的问题类型。",
                            "suggestion": "无。",
                            "confidence": 0.8,
                        }
                    ],
                    "summary": "无效输出。",
                }
            )


class QuestionAnalysisRuleTests(unittest.TestCase):
    def test_linked_image_prevents_model_only_missing_image_issue(self):
        model_issue = QualityIssue(
            issue_type=QualityIssueType.MISSING_IMAGE,
            severity=QualitySeverity.ERROR,
            location="question",
            description="模型无法查看图片内容。",
            suggestion="补充图片。",
            confidence=0.8,
        )

        merged = _merge_quality_issues(
            [],
            [model_issue],
            question_has_images=True,
        )

        self.assertEqual(merged, [])

    def test_missing_image_issue_is_kept_when_no_image_is_linked(self):
        deterministic_issue = QualityIssue(
            issue_type=QualityIssueType.MISSING_IMAGE,
            severity=QualitySeverity.ERROR,
            location="question",
            description="题目引用图片但未关联资源。",
            suggestion="补充图片。",
            confidence=1.0,
        )

        merged = _merge_quality_issues(
            [deterministic_issue],
            [],
            question_has_images=False,
        )

        self.assertEqual(merged, [deterministic_issue])


class QuestionAnalysisProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_falls_back_when_provider_rejects_json_schema(self):
        calls = []

        class FakeCompletions:
            async def create(self, **kwargs):
                calls.append(kwargs)
                if "response_format" in kwargs:
                    response = httpx.Response(
                        400,
                        request=httpx.Request("POST", "https://example.invalid"),
                    )
                    raise BadRequestError(
                        "response_format is unavailable",
                        response=response,
                        body={"error": {"message": "response_format is unavailable"}},
                    )
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                refusal=None,
                                content=json.dumps(
                                    {
                                        "difficulty_level": 2,
                                        "estimated_correct_rate": 0.75,
                                        "confidence": 0.8,
                                        "rationale": "基础理解题。",
                                    },
                                    ensure_ascii=False,
                                ),
                            )
                        )
                    ]
                )

        class FakeClient:
            def __init__(self):
                self.chat = SimpleNamespace(completions=FakeCompletions())
                self.closed = False

            async def close(self):
                self.closed = True

        client = FakeClient()
        with (
            patch.object(settings, "openai_api_key", "test-key"),
            patch(
                "app.modules.paper_agent.services.question_analysis.get_llm",
                return_value=client,
            ),
        ):
            result = await _complete_analysis(
                [{"role": "user", "content": "测试题"}],
                _difficulty_response_format(),
            )

        self.assertIn("response_format", calls[0])
        self.assertNotIn("response_format", calls[1])
        self.assertIn("JSON Schema", calls[1]["messages"][-1]["content"])
        self.assertIn('"difficulty_level": 2', result)
        self.assertTrue(client.closed)


class QuestionAnalysisServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.source_id = str(uuid.uuid4())
        self.question_id = str(uuid.uuid4())
        source = QuestionSource(
            source_id=self.source_id,
            source_type=SourceType.MANUAL,
            name="BIO-027/028 analysis fixture",
            external_id=self.source_id,
        )
        question = Question(
            id=self.question_id,
            question_type=QuestionType.SINGLE_CHOICE,
            stem="根据下图，判断某种膜蛋白运输物质的机制。",
            source=source,
            options=[
                QuestionOption(label="A", content="自由扩散"),
                QuestionOption(label="B", content="主动运输"),
            ],
            answer=None,
            explanation="需要结合图示判断。",
        )
        async with self.sessions() as session:
            context = QuestionPersistenceContext(session)
            await context.save_question(question)
            session.add_all(
                [
                    QuestionKnowledgePointModel(
                        question_id=self.question_id,
                        knowledge_point_code="BIO-M1-K03",
                    ),
                    QuestionCoreCompetencyModel(
                        question_id=self.question_id,
                        competency_code="BIO-C2",
                    ),
                ]
            )
            await session.commit()

    async def asyncTearDown(self):
        async with self.sessions() as session:
            await session.execute(
                delete(QuestionModel).where(QuestionModel.id == self.question_id)
            )
            await session.execute(
                delete(QuestionSourceModel).where(
                    QuestionSourceModel.source_id == self.source_id
                )
            )
            await session.commit()
        await self.engine.dispose()

    async def test_estimates_level_and_correct_rate_and_saves_history(self):
        captured = {}

        async def completion(messages, response_format):
            captured["messages"] = messages
            captured["response_format"] = response_format
            return json.dumps(
                {
                    "difficulty_level": 4,
                    "estimated_correct_rate": 0.35,
                    "confidence": 0.88,
                    "rationale": "需要读取图示并完成跨膜运输机制的多步判断。",
                },
                ensure_ascii=False,
            )

        async with self.sessions() as session:
            result = await estimate_question_difficulty(
                session,
                self.question_id,
                completion=completion,
            )
            stored = await session.get(QuestionAnalysisModel, result.analysis_id)

        schema = captured["response_format"]["json_schema"]["schema"]
        self.assertEqual(
            schema["properties"]["difficulty_level"]["enum"],
            [1, 2, 3, 4, 5],
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("不可信数据", captured["messages"][0]["content"])
        self.assertEqual(result.difficulty_level, 4)
        self.assertEqual(result.estimated_correct_rate, 0.35)
        self.assertEqual(stored.analysis_type, "difficulty_estimation")
        self.assertEqual(stored.result["difficulty_level"], 4)

    async def test_invalid_difficulty_output_is_not_persisted(self):
        async def completion(messages, response_format):
            return json.dumps(
                {
                    "difficulty_level": 5,
                    "estimated_correct_rate": 0.95,
                    "confidence": 0.9,
                    "rationale": "冲突输出。",
                }
            )

        async with self.sessions() as session:
            with self.assertRaises(QuestionAnalysisOutputError):
                await estimate_question_difficulty(
                    session,
                    self.question_id,
                    completion=completion,
                )
            analyses = list(
                await session.scalars(
                    select(QuestionAnalysisModel).where(
                        QuestionAnalysisModel.question_id == self.question_id
                    )
                )
            )
        self.assertEqual(analyses, [])

    async def test_quality_review_combines_rules_and_strict_model_issues(self):
        async def completion(messages, response_format):
            return json.dumps(
                {
                    "issues": [
                        {
                            "issue_type": "missing_image",
                            "severity": "warning",
                            "location": "question",
                            "description": "模型也发现图缺失。",
                            "suggestion": "补图。",
                            "confidence": 0.8,
                        },
                        {
                            "issue_type": "ambiguity",
                            "severity": "error",
                            "location": "stem",
                            "description": "缺少图示导致运输条件不明确。",
                            "suggestion": "提供图示和物质浓度方向。",
                            "confidence": 0.93,
                        },
                        {
                            "issue_type": "out_of_scope",
                            "severity": "warning",
                            "location": "stem",
                            "description": "题目可能要求未给出的大学阶段膜动力学。",
                            "suggestion": "限定在高中跨膜运输模型内。",
                            "confidence": 0.72,
                        },
                    ],
                    "summary": "题目暂不适合直接进入组卷。",
                },
                ensure_ascii=False,
            )

        async with self.sessions() as session:
            result = await review_question_quality(
                session,
                self.question_id,
                completion=completion,
            )
            stored = await session.get(QuestionAnalysisModel, result.analysis_id)

        issue_types = {issue.issue_type.value for issue in result.issues}
        self.assertEqual(
            issue_types,
            {"missing_image", "missing_answer", "ambiguity", "out_of_scope"},
        )
        missing_image = next(
            issue
            for issue in result.issues
            if issue.issue_type.value == "missing_image"
        )
        self.assertEqual(missing_image.confidence, 1.0)
        self.assertFalse(result.passed)
        self.assertEqual(stored.analysis_type, "quality_review")
        self.assertFalse(stored.result["passed"])

    async def test_analysis_requires_both_taxonomy_dimensions(self):
        called = False

        async def completion(messages, response_format):
            nonlocal called
            called = True
            return "{}"

        async with self.sessions() as session:
            await session.execute(
                delete(QuestionCoreCompetencyModel).where(
                    QuestionCoreCompetencyModel.question_id == self.question_id
                )
            )
            await session.commit()
            with self.assertRaises(QuestionAnalysisPrerequisiteError):
                await estimate_question_difficulty(
                    session,
                    self.question_id,
                    completion=completion,
                )
        self.assertFalse(called)


if __name__ == "__main__":
    unittest.main()

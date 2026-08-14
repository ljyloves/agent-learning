import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.modules.paper_agent.schemas.conversation import PaperPlan
from app.modules.paper_agent.schemas.plan_parser import (
    PaperPlanDraft,
    PaperPlanParseStatus,
)
from app.modules.paper_agent.schemas.taxonomy import (
    BiologyTaxonomyResponse,
    CoreCompetencyRead,
    CurriculumModuleRead,
    KnowledgePointRead,
)
from app.modules.paper_agent.services.plan_parser import (
    _JSON_OBJECT_FALLBACK_PROFILES,
    _complete_draft,
    _strict_response_format,
    PaperPlanParserProviderError,
    normalize_paper_plan_draft,
    parse_paper_plan,
)


def taxonomy() -> BiologyTaxonomyResponse:
    return BiologyTaxonomyResponse(
        modules=[
            CurriculumModuleRead(
                code="BIO-M1",
                name="分子与细胞",
                course_type="required",
                description="细胞层次",
                sort_order=1,
                knowledge_points=[
                    KnowledgePointRead(
                        code="BIO-M1-K01",
                        name="细胞的分子组成",
                        description="组成细胞的物质",
                        sort_order=1,
                    ),
                    KnowledgePointRead(
                        code="BIO-M1-K02",
                        name="细胞基本结构",
                        description="细胞结构",
                        sort_order=2,
                    ),
                ],
            )
        ],
        core_competencies=[
            CoreCompetencyRead(
                code="BIO-C1",
                name="生命观念",
                description="生命观念",
                sort_order=1,
            )
        ],
    )


def complete_draft(**overrides) -> PaperPlanDraft:
    payload = {
        "paper_name": "细胞单元测验",
        "grade": "高一",
        "exam_type": "单元测验",
        "duration_minutes": 45,
        "module": "分子与细胞",
        "knowledge_points": ["细胞的分子组成", "BIO-M1-K02"],
        "quotas": [
            {
                "question_type": "单选",
                "difficulty_level": 2,
                "count": 2,
                "score_per_question": 5,
            }
        ],
        "stated_question_count": 2,
        "stated_total_score": 10,
    }
    payload.update(overrides)
    return PaperPlanDraft.model_validate(payload)


class PaperPlanParserTests(unittest.TestCase):
    def test_maps_names_to_real_codes_and_calculates_totals(self):
        result = normalize_paper_plan_draft(complete_draft(), taxonomy())

        self.assertEqual(result.status, PaperPlanParseStatus.READY)
        self.assertEqual(result.plan.optimization.module_code, "BIO-M1")
        self.assertEqual(result.plan.optimization.question_count, 2)
        self.assertEqual(result.plan.optimization.total_score, 10)
        self.assertEqual(
            [target.code for target in result.plan.optimization.coverage.targets],
            ["BIO-M1-K01", "BIO-M1-K02"],
        )

    def test_second_turn_preserves_omitted_previous_fields(self):
        initial = normalize_paper_plan_draft(complete_draft(), taxonomy()).plan
        update = PaperPlanDraft(
            duration_minutes=60,
            quotas=[
                {
                    "question_type": "single_choice",
                    "difficulty_level": 3,
                    "count": 2,
                    "score_per_question": 5,
                }
            ],
        )

        result = normalize_paper_plan_draft(
            update,
            taxonomy(),
            previous_plan=PaperPlan.model_validate(initial),
        )

        self.assertEqual(result.status, PaperPlanParseStatus.READY)
        self.assertEqual(result.plan.paper_info.duration_minutes, 60)
        self.assertEqual(result.plan.paper_info.paper_name, "细胞单元测验")
        self.assertEqual(result.plan.optimization.module_code, "BIO-M1")

    def test_unknown_taxonomy_label_never_enters_plan(self):
        result = normalize_paper_plan_draft(
            complete_draft(knowledge_points=["模型虚构知识点"]),
            taxonomy(),
        )

        self.assertEqual(result.status, PaperPlanParseStatus.NEEDS_CLARIFICATION)
        self.assertIsNone(result.plan)
        self.assertIn("找不到", result.clarification_questions[0])

    def test_conflicting_question_count_and_score_require_clarification(self):
        result = normalize_paper_plan_draft(
            complete_draft(stated_question_count=3, stated_total_score=20),
            taxonomy(),
        )

        self.assertEqual(result.status, PaperPlanParseStatus.NEEDS_CLARIFICATION)
        self.assertEqual(len(result.clarification_questions), 2)

    def test_common_teacher_question_type_names_are_normalized(self):
        result = normalize_paper_plan_draft(
            complete_draft(
                quotas=[
                    {
                        "question_type": "单选题",
                        "difficulty_level": 3,
                        "count": 1,
                        "score_per_question": 5,
                    },
                    {
                        "question_type": "非选择题",
                        "difficulty_level": 3,
                        "count": 1,
                        "score_per_question": 15,
                    },
                ],
                stated_question_count=2,
                stated_total_score=20,
            ),
            taxonomy(),
        )

        self.assertEqual(result.status, PaperPlanParseStatus.READY)
        self.assertEqual(
            [quota.question_type.value for quota in result.plan.optimization.difficulty_quotas],
            ["single_choice", "composite"],
        )

    def test_invalid_update_keeps_previous_plan_for_form_fallback(self):
        previous = normalize_paper_plan_draft(complete_draft(), taxonomy()).plan
        result = normalize_paper_plan_draft(
            PaperPlanDraft(knowledge_points=["不存在"]),
            taxonomy(),
            previous_plan=previous,
        )

        self.assertEqual(result.previous_plan, previous)
        self.assertIsNone(result.plan)


class FakeProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def completion_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class PaperPlanProviderCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _JSON_OBJECT_FALLBACK_PROFILES.clear()

    def tearDown(self):
        _JSON_OBJECT_FALLBACK_PROFILES.clear()

    async def test_json_schema_rejection_retries_with_json_object(self):
        draft_json = json.dumps(
            complete_draft().model_dump(mode="json"),
            ensure_ascii=False,
        )
        create = AsyncMock(
            side_effect=[
                FakeProviderError("This response_format type is unavailable now"),
                completion_response(draft_json),
            ]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create),
            ),
            close=AsyncMock(),
        )

        with (
            patch(
                "app.modules.paper_agent.services.plan_parser.get_llm",
                return_value=client,
            ),
            patch(
                "app.modules.paper_agent.services.plan_parser.settings.openai_api_key",
                "test-key",
            ),
            patch(
                "app.modules.paper_agent.services.plan_parser.settings.openai_base_url",
                "https://provider.example/v1",
            ),
            patch(
                "app.modules.paper_agent.services.plan_parser.settings.paper_agent_model",
                "provider-model",
            ),
        ):
            content = await _complete_draft(
                [{"role": "system", "content": "Return JSON."}],
                _strict_response_format(),
            )

        self.assertEqual(content, draft_json)
        self.assertEqual(create.await_count, 2)
        self.assertEqual(
            create.await_args_list[0].kwargs["response_format"]["type"],
            "json_schema",
        )
        fallback_call = create.await_args_list[1].kwargs
        self.assertEqual(fallback_call["response_format"], {"type": "json_object"})
        self.assertIn("required", fallback_call["messages"][0]["content"])
        client.close.assert_awaited_once()

    async def test_known_profile_uses_json_object_without_repeating_rejection(self):
        profile = ("https://provider.example/v1", "provider-model")
        _JSON_OBJECT_FALLBACK_PROFILES.add(profile)
        create = AsyncMock(return_value=completion_response("{}"))
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create),
            ),
            close=AsyncMock(),
        )

        with (
            patch(
                "app.modules.paper_agent.services.plan_parser.get_llm",
                return_value=client,
            ),
            patch(
                "app.modules.paper_agent.services.plan_parser.settings.openai_api_key",
                "test-key",
            ),
            patch(
                "app.modules.paper_agent.services.plan_parser.settings.openai_base_url",
                profile[0],
            ),
            patch(
                "app.modules.paper_agent.services.plan_parser.settings.paper_agent_model",
                profile[1],
            ),
        ):
            await _complete_draft(
                [{"role": "system", "content": "Return JSON."}],
                _strict_response_format(),
            )

        self.assertEqual(create.await_count, 1)
        self.assertEqual(
            create.await_args.kwargs["response_format"],
            {"type": "json_object"},
        )

    async def test_unrelated_provider_error_is_not_retried(self):
        create = AsyncMock(side_effect=FakeProviderError("model not found"))
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create),
            ),
            close=AsyncMock(),
        )

        with (
            patch(
                "app.modules.paper_agent.services.plan_parser.get_llm",
                return_value=client,
            ),
            patch(
                "app.modules.paper_agent.services.plan_parser.settings.openai_api_key",
                "test-key",
            ),
        ):
            with self.assertRaises(PaperPlanParserProviderError):
                await _complete_draft(
                    [{"role": "system", "content": "Return JSON."}],
                    _strict_response_format(),
                )

        self.assertEqual(create.await_count, 1)
        client.close.assert_awaited_once()

    async def test_provider_failure_preserves_plan_and_explains_model_issue(self):
        previous = normalize_paper_plan_draft(complete_draft(), taxonomy()).plan

        async def fail_completion(*_):
            raise PaperPlanParserProviderError("provider failed")

        with patch(
            "app.modules.paper_agent.services.plan_parser.get_biology_taxonomy",
            new=AsyncMock(return_value=taxonomy()),
        ):
            result = await parse_paper_plan(
                None,
                "继续修改",
                previous_plan=previous,
                complete=fail_completion,
            )

        self.assertEqual(result.status, PaperPlanParseStatus.FORM_FALLBACK)
        self.assertEqual(result.previous_plan, previous)
        self.assertIn("模型服务", result.clarification_questions[0])


if __name__ == "__main__":
    unittest.main()

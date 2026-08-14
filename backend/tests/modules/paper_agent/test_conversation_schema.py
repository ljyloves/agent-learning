import unittest

from pydantic import ValidationError

from app.modules.paper_agent.schemas.conversation import (
    ConversationMessageCreate,
    PaperPlan,
)
from app.modules.paper_agent.schemas.conversation_graph import (
    ConversationGraphState,
    ConversationGraphStatus,
)


def valid_plan_payload() -> dict:
    return {
        "paper_info": {
            "paper_name": "高一生物单元测试",
            "grade": "高一",
            "exam_type": "单元测试",
            "duration_minutes": 60,
        },
        "optimization": {
            "module_code": "BIO-M1",
            "question_count": 2,
            "total_score": 10,
            "difficulty_quotas": [
                {
                    "question_type": "single_choice",
                    "difficulty_level": 2,
                    "count": 2,
                    "score_per_question": 5,
                }
            ],
            "coverage": {
                "targets": [
                    {"code": "BIO-M1-K01", "minimum_count": 1},
                    {"code": "BIO-M1-K02", "minimum_count": 1},
                ],
                "minimum_coverage_rate": 1.0,
            },
            "diversity": {
                "minimum_distinct_knowledge_points": 2,
                "minimum_distinct_core_competencies": 1,
                "minimum_distinct_sources": 1,
            },
        },
    }


class ConversationSchemaTests(unittest.TestCase):
    def test_paper_plan_is_the_existing_task_contract(self):
        plan = PaperPlan.model_validate(valid_plan_payload())

        task = plan.to_task_create()

        self.assertEqual(task.optimization.question_count, 2)
        self.assertEqual(task.paper_info.paper_name, "高一生物单元测试")

    def test_paper_plan_rejects_partial_or_inconsistent_constraints(self):
        payload = valid_plan_payload()
        payload["optimization"]["question_count"] = 3

        with self.assertRaises(ValidationError):
            PaperPlan.model_validate(payload)

    def test_message_requires_nonblank_bounded_content(self):
        with self.assertRaises(ValidationError):
            ConversationMessageCreate(message_id="msg-1", content="")
        with self.assertRaises(ValidationError):
            ConversationMessageCreate(message_id="msg-1", content="x" * 20_001)

    def test_database_identifiers_reject_values_longer_than_columns(self):
        with self.assertRaises(ValidationError):
            ConversationMessageCreate(
                message_id="conversation-" + "a" * 36,
                content="组卷",
            )

    def test_completed_non_paper_action_requires_action_but_not_job(self):
        state = ConversationGraphState(
            conversation_id="conv-1",
            message_id="msg-1",
            pending_action_id="action-1",
            status=ConversationGraphStatus.COMPLETED,
        )

        self.assertIsNone(state.paper_job_id)
        with self.assertRaises(ValidationError):
            ConversationGraphState(
                conversation_id="conv-1",
                message_id="msg-1",
                status=ConversationGraphStatus.COMPLETED,
            )


if __name__ == "__main__":
    unittest.main()

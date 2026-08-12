import unittest

from pydantic import ValidationError

from app.modules.paper_agent.schemas.optimization import (
    CoverageConstraint,
    DifficultyQuota,
    DiversityConstraint,
    KnowledgePointTarget,
    OptimizedPaperRequest,
)
from app.modules.paper_agent.schemas.question import QuestionType


def request_payload(**overrides):
    payload = {
        "module_code": "BIO-M1",
        "question_count": 2,
        "total_score": 8,
        "difficulty_quotas": [
            DifficultyQuota(
                question_type=QuestionType.SINGLE_CHOICE,
                difficulty_level=2,
                count=2,
                score_per_question=4,
            )
        ],
        "coverage": CoverageConstraint(
            targets=[
                KnowledgePointTarget(code="BIO-M1-K01"),
                KnowledgePointTarget(code="BIO-M1-K02"),
            ]
        ),
        "diversity": DiversityConstraint(
            minimum_distinct_knowledge_points=2,
            minimum_distinct_core_competencies=2,
            minimum_distinct_sources=1,
        ),
    }
    payload.update(overrides)
    return payload


class OptimizationSchemaTests(unittest.TestCase):
    def test_accepts_strict_multi_constraint_request(self):
        request = OptimizedPaperRequest(**request_payload())

        self.assertEqual(request.question_count, 2)
        self.assertEqual(request.coverage.minimum_coverage_rate, 1.0)

    def test_rejects_duplicate_difficulty_quota(self):
        quota = request_payload()["difficulty_quotas"][0]
        with self.assertRaises(ValidationError):
            OptimizedPaperRequest(
                **request_payload(
                    question_count=4,
                    total_score=16,
                    difficulty_quotas=[quota, quota],
                )
            )

    def test_rejects_incorrect_count_or_score(self):
        with self.assertRaises(ValidationError):
            OptimizedPaperRequest(**request_payload(question_count=3))
        with self.assertRaises(ValidationError):
            OptimizedPaperRequest(**request_payload(total_score=9))

    def test_rejects_impossible_declared_diversity(self):
        with self.assertRaises(ValidationError):
            OptimizedPaperRequest(
                **request_payload(
                    diversity=DiversityConstraint(
                        minimum_distinct_knowledge_points=3,
                        minimum_distinct_core_competencies=2,
                        minimum_distinct_sources=1,
                    )
                )
            )


if __name__ == "__main__":
    unittest.main()

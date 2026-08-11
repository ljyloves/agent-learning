import unittest

from app.modules.paper_agent.services.deduplication import (
    DeduplicationCandidate,
    deduplicate_candidates,
)


class QuestionDeduplicationTests(unittest.TestCase):
    def test_removes_exact_and_highly_similar_questions_below_two_percent(self):
        candidates = [
            DeduplicationCandidate(
                question_id="q1",
                question_type="single_choice",
                content="细胞膜的基本支架是磷脂双分子层。\nA. 正确\nB. 错误",
            ),
            DeduplicationCandidate(
                question_id="q2",
                question_type="single_choice",
                content="细胞膜的基本支架是：磷脂双分子层！ A 正确 B 错误",
            ),
            DeduplicationCandidate(
                question_id="q3",
                question_type="single_choice",
                content="细胞膜的基本骨架由磷脂双分子层构成。\nA. 正确\nB. 错误",
            ),
            DeduplicationCandidate(
                question_id="q4",
                question_type="single_choice",
                content="线粒体是有氧呼吸的主要场所。\nA. 正确\nB. 错误",
            ),
        ]
        result = deduplicate_candidates(
            candidates,
            [[1.0, 0.0], [1.0, 0.0], [0.99, 0.01], [0.0, 1.0]],
            semantic_similarity_threshold=0.94,
        )

        self.assertEqual(result.retained_ids, ("q1", "q4"))
        self.assertEqual(result.report.exact_duplicate_count, 1)
        self.assertEqual(result.report.semantic_duplicate_count, 1)
        self.assertEqual(result.report.retained_count, 2)
        self.assertEqual(result.report.output_count, 2)
        self.assertLess(result.report.remaining_duplicate_ratio, 0.02)
        self.assertEqual(
            [match.kind for match in result.report.matches],
            ["exact", "semantic"],
        )

    def test_does_not_merge_different_question_types(self):
        candidates = [
            DeduplicationCandidate("q1", "single_choice", "细胞膜结构"),
            DeduplicationCandidate("q2", "short_answer", "细胞膜结构"),
        ]
        result = deduplicate_candidates(
            candidates,
            [[1.0, 0.0], [1.0, 0.0]],
            semantic_similarity_threshold=0.94,
        )
        self.assertEqual(result.retained_ids, ("q1", "q2"))


if __name__ == "__main__":
    unittest.main()

import unittest

from pydantic import ValidationError

from app.modules.paper_agent.schemas.task import PaperTaskCreate, PaperTaskReview


class PaperTaskSchemaTests(unittest.TestCase):
    def test_create_reuses_strict_assembly_validation(self):
        with self.assertRaises(ValidationError):
            PaperTaskCreate(
                assembly={
                    "module_code": "BIO-M1",
                    "question_count": 2,
                    "total_score": 5,
                    "sections": [
                        {
                            "question_type": "single_choice",
                            "difficulty": "easy",
                            "count": 1,
                            "score_per_question": 5,
                        }
                    ],
                }
            )

    def test_review_reuses_teacher_action_validation(self):
        with self.assertRaises(ValidationError):
            PaperTaskReview(action="reject", reviewer="teacher-1")


if __name__ == "__main__":
    unittest.main()

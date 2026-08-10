import unittest

from pydantic import ValidationError

from app.modules.paper_agent.schemas import PaperJobQuestionCreate


def payload() -> dict:
    source = {
        "source_id": "bio011-source",
        "source_type": "website",
        "name": "Biology Question Bank",
        "uri": "https://example.edu/biology/1",
    }
    return {
        "job": {"job_id": "bio011-job"},
        "question": {
            "id": "bio011-question",
            "question_type": "single_choice",
            "stem": "Which organelle is the main site of aerobic respiration?",
            "source": source,
            "options": [
                {"label": "A", "content": "Mitochondrion"},
                {"label": "B", "content": "Ribosome"},
            ],
            "answer": "A",
            "explanation": "Aerobic respiration mainly occurs in mitochondria.",
        },
        "knowledge_point_codes": ["BIO-M1-K05"],
        "core_competency_codes": ["BIO-C1"],
    }


class TaxonomySchemaTests(unittest.TestCase):
    def test_job_question_request_accepts_structured_question(self):
        request = PaperJobQuestionCreate.model_validate(payload())

        self.assertEqual(request.job.job_id, "bio011-job")
        self.assertEqual(request.question.options[0].label, "A")
        self.assertEqual(request.knowledge_point_codes, ["BIO-M1-K05"])

    def test_job_question_request_rejects_duplicate_tags(self):
        duplicate = payload()
        duplicate["knowledge_point_codes"] = [
            "BIO-M1-K05",
            "BIO-M1-K05",
        ]

        with self.assertRaises(ValidationError):
            PaperJobQuestionCreate.model_validate(duplicate)


if __name__ == "__main__":
    unittest.main()

import unittest

from pydantic import ValidationError

from app.modules.paper_agent.graph import PaperGraphDecision
from app.modules.paper_agent.schemas.checkpoint import (
    PaperGraphTaskResume,
    PaperGraphTaskStart,
)


class PaperGraphCheckpointSchemaTests(unittest.TestCase):
    def test_replace_decision_requires_both_question_ids(self):
        request = PaperGraphTaskResume(
            decision=PaperGraphDecision.REPLACE,
            replace_question_id="question-1",
            replacement_question_id="question-2",
        )
        self.assertEqual(request.replace_question_id, "question-1")

        with self.assertRaises(ValidationError):
            PaperGraphTaskResume(
                decision=PaperGraphDecision.REPLACE,
                replace_question_id="question-1",
            )

    def test_non_replace_decision_rejects_replacement_ids(self):
        with self.assertRaises(ValidationError):
            PaperGraphTaskResume(
                decision=PaperGraphDecision.PASS,
                replace_question_id="question-1",
                replacement_question_id="question-2",
            )

    def test_error_code_is_only_valid_for_failure(self):
        failure = PaperGraphTaskResume(
            decision=PaperGraphDecision.FAIL,
            error_code="QUALITY_FAILED",
        )
        self.assertEqual(failure.error_code, "QUALITY_FAILED")

        with self.assertRaises(ValidationError):
            PaperGraphTaskResume(
                decision=PaperGraphDecision.RETRY,
                error_code="RETRY_REASON",
            )

    def test_start_request_validates_selected_candidate_relation(self):
        with self.assertRaises(ValidationError):
            PaperGraphTaskStart(
                job_id="job-invalid-selection",
                decision=PaperGraphDecision.RETRY,
                candidate_question_ids=["question-1"],
                selected_question_ids=["question-2"],
            )


if __name__ == "__main__":
    unittest.main()

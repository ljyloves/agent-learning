import unittest

from pydantic import ValidationError

from app.modules.paper_agent.schemas.checkpoint import (
    TeacherReviewCommand,
    TeacherReviewTaskStart,
)


class TeacherReviewSchemaTests(unittest.TestCase):
    def test_start_requires_selected_questions_to_be_candidates(self):
        with self.assertRaises(ValidationError):
            TeacherReviewTaskStart(
                job_id="job-1",
                paper_id="paper-1",
                candidate_question_ids=["question-1"],
                selected_question_ids=["question-2"],
            )

    def test_reject_requires_comment(self):
        with self.assertRaises(ValidationError):
            TeacherReviewCommand(action="reject", reviewer="teacher-1")

    def test_replace_requires_distinct_old_and_new_questions(self):
        with self.assertRaises(ValidationError):
            TeacherReviewCommand(
                action="replace",
                reviewer="teacher-1",
                replace_question_id="question-1",
                replacement_question_id="question-1",
            )

    def test_approve_rejects_replacement_fields(self):
        with self.assertRaises(ValidationError):
            TeacherReviewCommand(
                action="approve",
                reviewer="teacher-1",
                replace_question_id="question-1",
                replacement_question_id="question-2",
            )


if __name__ == "__main__":
    unittest.main()

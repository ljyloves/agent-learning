import unittest

from pydantic import ValidationError

from app.modules.paper_agent.graph import (
    PaperGraphDecision,
    PaperGraphExecution,
    PaperGraphReport,
    PaperGraphState,
)
from app.modules.paper_agent.schemas import PaperJobStatus


class PaperGraphStateTests(unittest.TestCase):
    def test_state_contains_only_ids_reports_and_execution(self):
        state = PaperGraphState(
            job_id="job-012",
            paper_id="paper-012",
            candidate_question_ids=["question-1", "question-2"],
            selected_question_ids=["question-2"],
            reports=[
                PaperGraphReport(
                    report_id="report-1",
                    stage="retrieve",
                    summary="Two candidate questions were retrieved.",
                    metrics={"candidate_count": 2},
                )
            ],
            execution=PaperGraphExecution(
                status=PaperJobStatus.RUNNING,
                current_node="retrieve",
                attempt=1,
            ),
        )

        self.assertEqual(
            set(state.model_dump()),
            {
                "job_id",
                "paper_id",
                "candidate_question_ids",
                "selected_question_ids",
                "reports",
                "execution",
            },
        )
        self.assertNotIn("stem", state.model_dump_json())
        self.assertNotIn("source", state.model_dump_json())

    def test_state_rejects_embedded_question_payload(self):
        with self.assertRaises(ValidationError):
            PaperGraphState.model_validate(
                {
                    "job_id": "job-rich-state",
                    "question": {"id": "question-1", "stem": "Rich payload"},
                }
            )

    def test_report_rejects_nested_domain_payload(self):
        with self.assertRaises(ValidationError):
            PaperGraphReport.model_validate(
                {
                    "report_id": "report-rich",
                    "stage": "retrieve",
                    "summary": "Invalid report payload.",
                    "metrics": {
                        "question": {"id": "question-1", "stem": "Payload"}
                    },
                }
            )

    def test_selected_questions_must_reference_candidates(self):
        with self.assertRaises(ValidationError):
            PaperGraphState(
                job_id="job-invalid-selection",
                candidate_question_ids=["question-1"],
                selected_question_ids=["question-2"],
            )

    def test_failed_execution_requires_error_code(self):
        with self.assertRaises(ValidationError):
            PaperGraphExecution(status=PaperJobStatus.FAILED)

        execution = PaperGraphExecution(
            status=PaperJobStatus.FAILED,
            current_node="retrieve",
            error_code="SOURCE_TIMEOUT",
        )
        self.assertEqual(execution.error_code, "SOURCE_TIMEOUT")

    def test_execution_tracks_bounded_branch_control_data(self):
        execution = PaperGraphExecution(
            status=PaperJobStatus.QUEUED,
            current_node="retry",
            attempt=2,
            decision=PaperGraphDecision.RETRY,
            retry_count=1,
            replacement_count=2,
        )

        self.assertEqual(execution.decision, PaperGraphDecision.RETRY)
        self.assertEqual(execution.retry_count, 1)
        self.assertEqual(execution.replacement_count, 2)

        with self.assertRaises(ValidationError):
            PaperGraphExecution(retry_count=101)

    def test_state_bounds_checkpoint_collections(self):
        with self.assertRaises(ValidationError):
            PaperGraphState(
                job_id="job-too-many-candidates",
                candidate_question_ids=[
                    f"question-{index}" for index in range(1001)
                ],
            )

        with self.assertRaises(ValidationError):
            PaperGraphReport(
                report_id="report-too-many-metrics",
                stage="evaluate",
                summary="The report exceeds the metric limit.",
                metrics={f"metric-{index}": index for index in range(101)},
            )


if __name__ == "__main__":
    unittest.main()

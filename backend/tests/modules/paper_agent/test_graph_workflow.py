import unittest

from pydantic import ValidationError

from app.modules.paper_agent.graph import (
    MAX_RETRY_ATTEMPTS,
    PaperGraphDecision,
    PaperGraphExecution,
    PaperGraphReport,
    PaperGraphState,
    paper_agent_graph,
)
from app.modules.paper_agent.schemas import PaperJobStatus


def quality_gate_report(
    decision: PaperGraphDecision,
    *,
    report_id: str,
    **metrics: str,
) -> PaperGraphReport:
    return PaperGraphReport(
        report_id=report_id,
        stage="quality_gate",
        summary=f"Quality gate requested {decision.value}.",
        metrics={"decision": decision.value, **metrics},
    )


class PaperGraphWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_graph_uses_pass_branch_by_default(self):
        result = await paper_agent_graph.ainvoke(
            PaperGraphState(
                job_id="job-graph-pass",
                candidate_question_ids=["question-1", "question-2"],
            )
        )
        state = PaperGraphState.model_validate(result)

        self.assertEqual(state.execution.status, PaperJobStatus.COMPLETED)
        self.assertEqual(state.execution.current_node, "complete")
        self.assertEqual(state.execution.decision, PaperGraphDecision.PASS)
        self.assertEqual(state.execution.attempt, 1)
        self.assertEqual(
            [report.stage for report in state.reports],
            ["initialize", "workflow_decision", "complete"],
        )
        self.assertEqual(state.candidate_question_ids, ["question-1", "question-2"])

    async def test_graph_handles_explicit_failure(self):
        result = await paper_agent_graph.ainvoke(
            PaperGraphState(
                job_id="job-graph-fail",
                reports=[
                    quality_gate_report(
                        PaperGraphDecision.FAIL,
                        report_id="quality-gate-fail",
                        error_code="ANSWER_VALIDATION_FAILED",
                    )
                ],
            )
        )
        state = PaperGraphState.model_validate(result)

        self.assertEqual(state.execution.status, PaperJobStatus.FAILED)
        self.assertEqual(state.execution.current_node, "fail")
        self.assertEqual(state.execution.error_code, "ANSWER_VALIDATION_FAILED")
        self.assertEqual(state.reports[-1].stage, "fail")

    async def test_graph_queues_retry_and_can_resume(self):
        first_result = await paper_agent_graph.ainvoke(
            PaperGraphState(
                job_id="job-graph-retry",
                reports=[
                    quality_gate_report(
                        PaperGraphDecision.RETRY,
                        report_id="quality-gate-retry-1",
                    )
                ],
            )
        )
        retry_state = PaperGraphState.model_validate(first_result)

        self.assertEqual(retry_state.execution.status, PaperJobStatus.QUEUED)
        self.assertEqual(retry_state.execution.current_node, "retry")
        self.assertEqual(retry_state.execution.retry_count, 1)

        resumed_state = PaperGraphState(
            **retry_state.model_dump(exclude={"reports"}),
            reports=[
                *retry_state.reports,
                quality_gate_report(
                    PaperGraphDecision.PASS,
                    report_id="quality-gate-retry-2",
                ),
            ],
        )
        second_result = await paper_agent_graph.ainvoke(resumed_state)
        completed_state = PaperGraphState.model_validate(second_result)

        self.assertEqual(completed_state.execution.status, PaperJobStatus.COMPLETED)
        self.assertEqual(completed_state.execution.attempt, 2)
        self.assertEqual(completed_state.execution.retry_count, 1)

    async def test_graph_fails_after_retry_limit(self):
        result = await paper_agent_graph.ainvoke(
            PaperGraphState(
                job_id="job-graph-retry-exhausted",
                reports=[
                    quality_gate_report(
                        PaperGraphDecision.RETRY,
                        report_id="quality-gate-retry-exhausted",
                    )
                ],
                execution=PaperGraphExecution(
                    retry_count=MAX_RETRY_ATTEMPTS,
                ),
            )
        )
        state = PaperGraphState.model_validate(result)

        self.assertEqual(state.execution.status, PaperJobStatus.FAILED)
        self.assertEqual(state.execution.current_node, "fail")
        self.assertEqual(state.execution.retry_count, MAX_RETRY_ATTEMPTS)
        self.assertEqual(state.execution.error_code, "RETRY_LIMIT_EXCEEDED")

    async def test_graph_replaces_selected_question_and_queues_review(self):
        result = await paper_agent_graph.ainvoke(
            PaperGraphState(
                job_id="job-graph-replace",
                candidate_question_ids=["question-1", "question-2", "question-3"],
                selected_question_ids=["question-1", "question-2"],
                reports=[
                    quality_gate_report(
                        PaperGraphDecision.REPLACE,
                        report_id="quality-gate-replace",
                        replace_question_id="question-2",
                        replacement_question_id="question-3",
                    )
                ],
            )
        )
        state = PaperGraphState.model_validate(result)

        self.assertEqual(state.execution.status, PaperJobStatus.QUEUED)
        self.assertEqual(state.execution.current_node, "replace_question")
        self.assertEqual(state.execution.replacement_count, 1)
        self.assertEqual(
            state.selected_question_ids,
            ["question-1", "question-3"],
        )

    async def test_graph_rejects_invalid_replacement_instruction(self):
        with self.assertRaises(ValidationError):
            await paper_agent_graph.ainvoke(
                PaperGraphState(
                    job_id="job-graph-invalid-replace",
                    candidate_question_ids=["question-1", "question-2"],
                    selected_question_ids=["question-1"],
                    reports=[
                        quality_gate_report(
                            PaperGraphDecision.REPLACE,
                            report_id="quality-gate-invalid-replace",
                            replace_question_id="question-1",
                            replacement_question_id="missing-question",
                        )
                    ],
                )
            )


if __name__ == "__main__":
    unittest.main()

import unittest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.modules.paper_agent.graph.checkpoint import (
    CHECKPOINT_ALLOWED_MSGPACK_MODULES,
)
from app.modules.paper_agent.graph.workflow import build_teacher_review_graph
from app.modules.paper_agent.schemas.checkpoint import (
    TeacherReviewCommand,
    TeacherReviewTaskStart,
)
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus
from app.modules.paper_agent.services.checkpoint import (
    TeacherReviewNotPendingError,
    start_teacher_review,
    submit_teacher_review,
    teacher_review_thread_config,
)


def review_start() -> TeacherReviewTaskStart:
    return TeacherReviewTaskStart(
        job_id="job-teacher-review",
        paper_id="paper-teacher-review",
        candidate_question_ids=["question-1", "question-2", "question-3"],
        selected_question_ids=["question-1", "question-2"],
    )


class TeacherReviewWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        checkpointer = InMemorySaver(
            serde=JsonPlusSerializer(
                allowed_msgpack_modules=CHECKPOINT_ALLOWED_MSGPACK_MODULES,
            )
        )
        self.graph = build_teacher_review_graph(checkpointer)

    async def test_review_pauses_and_approve_completes(self):
        thread_id = "teacher-review-approve"
        paused = await start_teacher_review(self.graph, thread_id, review_start())
        snapshot = await self.graph.aget_state(
            teacher_review_thread_config(thread_id)
        )

        self.assertEqual(paused.execution.status, PaperJobStatus.AWAITING_REVIEW)
        self.assertEqual(paused.execution.current_node, "await_teacher_review")
        self.assertEqual(len(snapshot.interrupts), 1)
        self.assertEqual(snapshot.interrupts[0].value["kind"], "teacher_review")

        completed = await submit_teacher_review(
            self.graph,
            thread_id,
            TeacherReviewCommand(
                action="approve",
                reviewer="teacher-zhang",
                comment="Ready to publish.",
            ),
        )

        self.assertEqual(completed.execution.status, PaperJobStatus.COMPLETED)
        self.assertEqual(completed.execution.current_node, "complete")
        with self.assertRaises(TeacherReviewNotPendingError):
            await submit_teacher_review(
                self.graph,
                thread_id,
                TeacherReviewCommand(action="approve", reviewer="teacher-zhang"),
            )

    async def test_reject_finishes_with_teacher_error(self):
        thread_id = "teacher-review-reject"
        await start_teacher_review(self.graph, thread_id, review_start())

        rejected = await submit_teacher_review(
            self.graph,
            thread_id,
            TeacherReviewCommand(
                action="reject",
                reviewer="teacher-li",
                comment="Difficulty distribution is unsuitable.",
            ),
        )

        self.assertEqual(rejected.execution.status, PaperJobStatus.FAILED)
        self.assertEqual(rejected.execution.error_code, "TEACHER_REJECTED")
        self.assertEqual(rejected.execution.current_node, "fail")

    async def test_replace_updates_selection_and_pauses_again(self):
        thread_id = "teacher-review-replace"
        await start_teacher_review(self.graph, thread_id, review_start())

        replaced = await submit_teacher_review(
            self.graph,
            thread_id,
            TeacherReviewCommand(
                action="replace",
                reviewer="teacher-wang",
                comment="Replace the ambiguous question.",
                replace_question_id="question-2",
                replacement_question_id="question-3",
            ),
        )
        snapshot = await self.graph.aget_state(
            teacher_review_thread_config(thread_id)
        )

        self.assertEqual(replaced.execution.status, PaperJobStatus.AWAITING_REVIEW)
        self.assertEqual(replaced.selected_question_ids, ["question-1", "question-3"])
        self.assertEqual(replaced.execution.replacement_count, 1)
        self.assertEqual(len(snapshot.interrupts), 1)
        self.assertEqual(
            snapshot.interrupts[0].value["selected_question_ids"],
            ["question-1", "question-3"],
        )

        completed = await submit_teacher_review(
            self.graph,
            thread_id,
            TeacherReviewCommand(action="approve", reviewer="teacher-wang"),
        )
        self.assertEqual(completed.execution.status, PaperJobStatus.COMPLETED)
        self.assertEqual(completed.execution.replacement_count, 1)


if __name__ == "__main__":
    unittest.main()

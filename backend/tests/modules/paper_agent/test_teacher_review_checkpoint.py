import unittest
from uuid import uuid4

from app.modules.paper_agent.graph.checkpoint import create_paper_graph_runtime
from app.modules.paper_agent.schemas.checkpoint import (
    TeacherReviewCommand,
    TeacherReviewTaskStart,
)
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus
from app.modules.paper_agent.services.checkpoint import (
    get_teacher_review_state,
    start_teacher_review,
    submit_teacher_review,
    teacher_review_thread_id,
)


class PostgreSQLTeacherReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_interrupted_review_resumes_after_runtime_recreation(self):
        thread_id = f"teacher-review-restart-{uuid4()}"
        request = TeacherReviewTaskStart(
            job_id="job-teacher-review-restart",
            paper_id="paper-teacher-review-restart",
            candidate_question_ids=["question-1", "question-2"],
            selected_question_ids=["question-1"],
        )

        async with create_paper_graph_runtime() as first_runtime:
            paused = await start_teacher_review(
                first_runtime.teacher_review_graph,
                thread_id,
                request,
            )
            self.assertEqual(paused.execution.status, PaperJobStatus.AWAITING_REVIEW)

        async with create_paper_graph_runtime() as second_runtime:
            persisted = await get_teacher_review_state(
                second_runtime.teacher_review_graph,
                thread_id,
            )
            self.assertIsNotNone(persisted)
            self.assertEqual(
                persisted.execution.status,
                PaperJobStatus.AWAITING_REVIEW,
            )

            completed = await submit_teacher_review(
                second_runtime.teacher_review_graph,
                thread_id,
                TeacherReviewCommand(
                    action="approve",
                    reviewer="teacher-restart",
                ),
            )
            self.assertEqual(completed.execution.status, PaperJobStatus.COMPLETED)
            await second_runtime.checkpointer.adelete_thread(
                teacher_review_thread_id(thread_id)
            )


if __name__ == "__main__":
    unittest.main()

import unittest
from uuid import uuid4

from app.modules.paper_agent.graph import PaperGraphDecision
from app.modules.paper_agent.graph.checkpoint import create_paper_graph_runtime
from app.modules.paper_agent.schemas.checkpoint import (
    PaperGraphTaskResume,
    PaperGraphTaskStart,
)
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus
from app.modules.paper_agent.services.checkpoint import (
    GraphTaskAlreadyExistsError,
    GraphTaskNotFoundError,
    GraphTaskNotResumableError,
    get_graph_task_state,
    resume_graph_task,
    start_graph_task,
)


class PostgreSQLGraphCheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_task_resumes_after_runtime_recreation(self):
        thread_id = f"checkpoint-restart-{uuid4()}"

        async with create_paper_graph_runtime() as first_runtime:
            queued_state = await start_graph_task(
                first_runtime.graph,
                thread_id,
                PaperGraphTaskStart(
                    job_id="job-checkpoint-restart",
                    decision=PaperGraphDecision.RETRY,
                ),
            )
            self.assertEqual(queued_state.execution.status, PaperJobStatus.QUEUED)
            self.assertEqual(queued_state.execution.attempt, 1)

        async with create_paper_graph_runtime() as second_runtime:
            persisted_state = await get_graph_task_state(
                second_runtime.graph,
                thread_id,
            )
            self.assertIsNotNone(persisted_state)
            self.assertEqual(persisted_state.execution.retry_count, 1)

            completed_state = await resume_graph_task(
                second_runtime.graph,
                thread_id,
                PaperGraphTaskResume(decision=PaperGraphDecision.PASS),
            )
            self.assertEqual(
                completed_state.execution.status,
                PaperJobStatus.COMPLETED,
            )
            self.assertEqual(completed_state.execution.attempt, 2)
            self.assertEqual(completed_state.execution.retry_count, 1)
            await second_runtime.checkpointer.adelete_thread(thread_id)

    async def test_duplicate_start_and_completed_resume_are_rejected(self):
        thread_id = f"checkpoint-conflict-{uuid4()}"

        async with create_paper_graph_runtime() as runtime:
            request = PaperGraphTaskStart(
                job_id="job-checkpoint-conflict",
                decision=PaperGraphDecision.PASS,
            )
            completed_state = await start_graph_task(
                runtime.graph,
                thread_id,
                request,
            )
            self.assertEqual(
                completed_state.execution.status,
                PaperJobStatus.COMPLETED,
            )

            with self.assertRaises(GraphTaskAlreadyExistsError):
                await start_graph_task(runtime.graph, thread_id, request)
            with self.assertRaises(GraphTaskNotResumableError):
                await resume_graph_task(
                    runtime.graph,
                    thread_id,
                    PaperGraphTaskResume(decision=PaperGraphDecision.PASS),
                )
            await runtime.checkpointer.adelete_thread(thread_id)

    async def test_missing_thread_cannot_resume(self):
        thread_id = f"checkpoint-missing-{uuid4()}"

        async with create_paper_graph_runtime() as runtime:
            with self.assertRaises(GraphTaskNotFoundError):
                await resume_graph_task(
                    runtime.graph,
                    thread_id,
                    PaperGraphTaskResume(decision=PaperGraphDecision.PASS),
                )


if __name__ == "__main__":
    unittest.main()

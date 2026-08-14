import unittest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Command

from app.modules.paper_agent.graph.checkpoint import CHECKPOINT_ALLOWED_MSGPACK_MODULES
from app.modules.paper_agent.graph.conversation_workflow import (
    ConversationWorkflowHandlers,
    build_conversation_agent_graph,
)
from app.modules.paper_agent.schemas.conversation_graph import (
    ConversationGraphCommand,
    ConversationGraphState,
    ConversationGraphStatus,
)


async def identity_finish(state):
    return state


class HandlerFixture:
    def __init__(self, *, execution_failures=0):
        self.execution_failures = execution_failures
        self.confirmation_ids = []
        self.executions = 0

    async def parse(self, state):
        return state.model_copy(
            update={
                "plan_version": 1,
                "status": ConversationGraphStatus.CHECKING_FEASIBILITY,
            }
        )

    async def feasibility(self, state):
        return state

    async def prepare(self, state):
        action_id = f"action-{state.retry_count}"
        self.confirmation_ids.append(action_id)
        return state.model_copy(
            update={
                "pending_action_id": action_id,
                "status": ConversationGraphStatus.AWAITING_CONFIRMATION,
            }
        )

    async def command(self, state, command: ConversationGraphCommand):
        return state.model_copy(
            update={
                "status": (
                    ConversationGraphStatus.CANCELLED
                    if command.action == "cancel"
                    else ConversationGraphStatus.EXECUTING
                )
            }
        )

    async def execute(self, state):
        self.executions += 1
        if self.executions <= self.execution_failures:
            return state.model_copy(
                update={"status": ConversationGraphStatus.RETRYABLE}
            )
        return state.model_copy(
            update={
                "paper_job_id": "job-1",
                "status": ConversationGraphStatus.COMPLETED,
            }
        )

    async def retry(self, state):
        return await self.prepare(
            state.model_copy(update={"retry_count": state.retry_count + 1})
        )

    def handlers(self):
        return ConversationWorkflowHandlers(
            parse_and_merge=self.parse,
            check_feasibility=self.feasibility,
            prepare_confirmation=self.prepare,
            apply_command=self.command,
            execute=self.execute,
            prepare_retry=self.retry,
            finish=identity_finish,
        )


class ConversationWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def graph(self, fixture):
        return build_conversation_agent_graph(
            fixture.handlers(),
            InMemorySaver(
                serde=JsonPlusSerializer(
                    allowed_msgpack_modules=CHECKPOINT_ALLOWED_MSGPACK_MODULES,
                )
            ),
        )

    async def test_complete_plan_interrupts_before_any_execution(self):
        fixture = HandlerFixture()
        graph = self.graph(fixture)
        config = {"configurable": {"thread_id": "conv-confirm"}}

        await graph.ainvoke(
            ConversationGraphState(conversation_id="conv-1", message_id="msg-1"),
            config=config,
        )
        snapshot = await graph.aget_state(config)

        self.assertEqual(fixture.executions, 0)
        self.assertEqual(len(snapshot.interrupts), 1)
        self.assertEqual(snapshot.interrupts[0].value["action_id"], "action-0")

    async def test_agent_write_action_can_interrupt_without_plan_feasibility(self):
        fixture = HandlerFixture()

        async def prepare_direct_action(state):
            return state.model_copy(
                update={
                    "pending_action_id": "action-direct",
                    "status": ConversationGraphStatus.AWAITING_CONFIRMATION,
                }
            )

        fixture.parse = prepare_direct_action
        graph = self.graph(fixture)
        config = {"configurable": {"thread_id": "conv-direct-action"}}

        await graph.ainvoke(
            ConversationGraphState(conversation_id="conv-1", message_id="msg-1"),
            config=config,
        )
        snapshot = await graph.aget_state(config)

        self.assertEqual(fixture.confirmation_ids, [])
        self.assertEqual(snapshot.interrupts[0].value["action_id"], "action-direct")

    async def test_confirm_executes_once_and_completes(self):
        fixture = HandlerFixture()
        graph = self.graph(fixture)
        config = {"configurable": {"thread_id": "conv-execute"}}
        await graph.ainvoke(
            ConversationGraphState(conversation_id="conv-1", message_id="msg-1"),
            config=config,
        )

        result = await graph.ainvoke(Command(resume={"action": "confirm"}), config=config)

        state = ConversationGraphState.model_validate(result)
        self.assertEqual(state.status, ConversationGraphStatus.COMPLETED)
        self.assertEqual(state.paper_job_id, "job-1")
        self.assertEqual(fixture.executions, 1)

    async def test_cancel_never_executes(self):
        fixture = HandlerFixture()
        graph = self.graph(fixture)
        config = {"configurable": {"thread_id": "conv-cancel"}}
        await graph.ainvoke(
            ConversationGraphState(conversation_id="conv-1", message_id="msg-1"),
            config=config,
        )

        result = await graph.ainvoke(Command(resume={"action": "cancel"}), config=config)

        state = ConversationGraphState.model_validate(result)
        self.assertEqual(state.status, ConversationGraphStatus.CANCELLED)
        self.assertEqual(fixture.executions, 0)

    async def test_failed_execution_creates_new_confirmation_before_retry(self):
        fixture = HandlerFixture(execution_failures=1)
        graph = self.graph(fixture)
        config = {"configurable": {"thread_id": "conv-retry"}}
        await graph.ainvoke(
            ConversationGraphState(conversation_id="conv-1", message_id="msg-1"),
            config=config,
        )
        await graph.ainvoke(Command(resume={"action": "confirm"}), config=config)
        paused = await graph.aget_state(config)

        self.assertEqual(fixture.executions, 1)
        self.assertEqual(fixture.confirmation_ids, ["action-0", "action-1"])
        self.assertEqual(paused.interrupts[0].value["action_id"], "action-1")

        completed = await graph.ainvoke(Command(resume={"action": "retry"}), config=config)
        state = ConversationGraphState.model_validate(completed)
        self.assertEqual(state.status, ConversationGraphStatus.COMPLETED)
        self.assertEqual(fixture.executions, 2)


if __name__ == "__main__":
    unittest.main()

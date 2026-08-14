import unittest
from uuid import uuid4

from langgraph.types import Command

from app.modules.paper_agent.graph.checkpoint import create_paper_graph_runtime
from app.modules.paper_agent.graph.conversation_workflow import (
    build_conversation_agent_graph,
)
from app.modules.paper_agent.schemas.conversation_graph import (
    ConversationGraphState,
    ConversationGraphStatus,
)
from tests.modules.paper_agent.test_conversation_workflow import HandlerFixture


class PostgreSQLConversationCheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirmation_resumes_after_runtime_recreation(self):
        thread_id = f"conversation-restart-{uuid4()}"
        config = {"configurable": {"thread_id": thread_id}}
        fixture = HandlerFixture()

        async with create_paper_graph_runtime() as first_runtime:
            graph = build_conversation_agent_graph(
                fixture.handlers(),
                first_runtime.checkpointer,
            )
            await graph.ainvoke(
                ConversationGraphState(
                    conversation_id="conv-restart",
                    message_id="msg-restart",
                ),
                config=config,
            )
            paused = await graph.aget_state(config)
            self.assertEqual(len(paused.interrupts), 1)

        async with create_paper_graph_runtime() as second_runtime:
            graph = build_conversation_agent_graph(
                fixture.handlers(),
                second_runtime.checkpointer,
            )
            persisted = await graph.aget_state(config)
            self.assertEqual(
                persisted.interrupts[0].value["action_id"],
                "action-0",
            )
            result = await graph.ainvoke(
                Command(resume={"action": "confirm"}),
                config=config,
            )
            state = ConversationGraphState.model_validate(result)
            self.assertEqual(state.status, ConversationGraphStatus.COMPLETED)
            self.assertEqual(fixture.executions, 1)
            await second_runtime.checkpointer.adelete_thread(thread_id)


if __name__ == "__main__":
    unittest.main()

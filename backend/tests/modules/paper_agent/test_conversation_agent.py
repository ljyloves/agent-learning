import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.modules.paper_agent.schemas.conversation_agent import (
    ConversationAgentOutcomeKind,
)
from app.modules.paper_agent.services.conversation_agent import (
    PREPARE_PLAN_TOOL,
    run_conversation_agent,
)
from tests.modules.paper_agent.test_plan_parser import complete_draft, taxonomy


def tool_call(name: str, arguments: dict, call_id: str = "call-1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments, ensure_ascii=False),
        ),
    )


def model_response(*, content: str = "", tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls,
                )
            )
        ]
    )


def fake_client(*responses):
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(side_effect=list(responses)),
            )
        ),
        close=AsyncMock(),
    )


def fake_session(*, paper_job_id=None):
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(paper_job_id=paper_job_id)
    session.scalars.return_value = []
    return session


class ConversationAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_free_conversation_returns_model_reply_without_tool(self):
        client = fake_client(model_response(content="当然可以，我们先聊聊命题思路。"))

        with patch(
            "app.modules.paper_agent.services.conversation_agent.get_llm",
            return_value=client,
        ):
            outcome = await run_conversation_agent(
                fake_session(),
                "conv-1",
                previous_plan=None,
            )

        self.assertEqual(outcome.kind, ConversationAgentOutcomeKind.REPLY)
        self.assertIn("命题思路", outcome.reply)
        client.close.assert_awaited_once()

    async def test_read_tool_result_is_returned_to_model_for_final_reply(self):
        client = fake_client(
            model_response(tool_calls=[tool_call("query_taxonomy", {})]),
            model_response(content="当前包含分子与细胞等课程模块。"),
        )

        with (
            patch(
                "app.modules.paper_agent.services.conversation_agent.get_llm",
                return_value=client,
            ),
            patch(
                "app.modules.paper_agent.services.conversation_agent.controlled_tool_executor.execute",
                new=AsyncMock(return_value={"modules": []}),
            ) as execute,
        ):
            outcome = await run_conversation_agent(
                fake_session(),
                "conv-1",
                previous_plan=None,
            )

        self.assertEqual(outcome.kind, ConversationAgentOutcomeKind.REPLY)
        execute.assert_awaited_once()
        second_messages = client.chat.completions.create.await_args_list[1].kwargs[
            "messages"
        ]
        self.assertEqual(second_messages[-1]["role"], "tool")

    async def test_prepare_plan_tool_returns_validated_canonical_plan(self):
        client = fake_client(
            model_response(
                tool_calls=[
                    tool_call(
                        PREPARE_PLAN_TOOL,
                        complete_draft().model_dump(mode="json"),
                    )
                ]
            )
        )

        with (
            patch(
                "app.modules.paper_agent.services.conversation_agent.get_llm",
                return_value=client,
            ),
            patch(
                "app.modules.paper_agent.services.conversation_agent.get_biology_taxonomy",
                new=AsyncMock(return_value=taxonomy()),
            ),
        ):
            outcome = await run_conversation_agent(
                fake_session(),
                "conv-1",
                previous_plan=None,
            )

        self.assertEqual(outcome.kind, ConversationAgentOutcomeKind.PLAN)
        self.assertEqual(outcome.plan.optimization.module_code, "BIO-M1")
        self.assertEqual(outcome.plan.optimization.total_score, 10)

    async def test_write_tool_is_prepared_but_never_executed(self):
        client = fake_client(
            model_response(
                tool_calls=[tool_call("prepare_exports", {"job_id": "job-1"})]
            )
        )

        with (
            patch(
                "app.modules.paper_agent.services.conversation_agent.get_llm",
                return_value=client,
            ),
            patch(
                "app.modules.paper_agent.services.conversation_agent.controlled_tool_executor.execute",
                new=AsyncMock(),
            ) as execute,
        ):
            outcome = await run_conversation_agent(
                fake_session(paper_job_id="job-1"),
                "conv-1",
                previous_plan=None,
            )

        self.assertEqual(outcome.kind, ConversationAgentOutcomeKind.WRITE_ACTION)
        self.assertEqual(outcome.tool_name, "prepare_exports")
        self.assertEqual(outcome.tool_payload, {"job_id": "job-1"})
        execute.assert_not_awaited()

    async def test_taxonomy_write_is_prepared_but_never_executed(self):
        payload = {
            "change": {
                "action": "create_knowledge_point",
                "code": "BIO-M1-K99",
                "name": "细胞自噬",
                "description": "细胞通过溶酶体降解自身成分的过程。",
                "module_code": "BIO-M1",
            }
        }
        client = fake_client(
            model_response(
                tool_calls=[tool_call("apply_taxonomy_change", payload)]
            )
        )

        with (
            patch(
                "app.modules.paper_agent.services.conversation_agent.get_llm",
                return_value=client,
            ),
            patch(
                "app.modules.paper_agent.services.conversation_agent.controlled_tool_executor.execute",
                new=AsyncMock(),
            ) as execute,
        ):
            outcome = await run_conversation_agent(
                fake_session(),
                "conv-1",
                previous_plan=None,
            )

        self.assertEqual(outcome.kind, ConversationAgentOutcomeKind.WRITE_ACTION)
        self.assertEqual(outcome.tool_name, "apply_taxonomy_change")
        self.assertEqual(outcome.tool_payload["change"]["code"], "BIO-M1-K99")
        execute.assert_not_awaited()

    async def test_model_failure_keeps_structured_form_available(self):
        client = fake_client(RuntimeError("provider unavailable"))

        with patch(
            "app.modules.paper_agent.services.conversation_agent.get_llm",
            return_value=client,
        ):
            outcome = await run_conversation_agent(
                fake_session(),
                "conv-1",
                previous_plan=None,
            )

        self.assertEqual(outcome.kind, ConversationAgentOutcomeKind.FORM_FALLBACK)
        self.assertIn("结构化方案", outcome.reply)


if __name__ == "__main__":
    unittest.main()

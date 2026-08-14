import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx

from app.database import get_db
from app.main import app
from app.modules.paper_agent.conversation_router import get_conversation_graph
from app.modules.paper_agent.schemas.conversation import ConversationRead
from app.modules.paper_agent.schemas.conversation_graph import (
    ConversationGraphState,
    ConversationGraphStatus,
    ConversationGraphStatusResponse,
)
from app.modules.paper_agent.services.conversation_graph import (
    ConversationGraphNotInterruptedError,
)


def conversation() -> ConversationRead:
    now = datetime.now(timezone.utc)
    return ConversationRead(
        conversation_id="conv-api",
        title="细胞测试",
        status="active",
        active_plan_version=0,
        created_at=now,
        updated_at=now,
    )


def graph_status() -> ConversationGraphStatusResponse:
    return ConversationGraphStatusResponse(
        state=ConversationGraphState(
            conversation_id="conv-api",
            message_id="msg-api",
            plan_version=1,
            pending_action_id="action-api",
            status=ConversationGraphStatus.AWAITING_CONFIRMATION,
        ),
        interrupted=True,
        interrupt_payload={"kind": "paper_plan_confirmation"},
    )


class ConversationApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = AsyncMock()
        self.graph = AsyncMock()

        async def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_conversation_graph] = lambda: self.graph
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()

    def test_openapi_exposes_complete_conversation_surface(self):
        paths = app.openapi()["paths"]
        expected = {
            "/api/paper-agent/conversations",
            "/api/paper-agent/conversations/{conversation_id}",
            "/api/paper-agent/conversations/{conversation_id}/history",
            "/api/paper-agent/conversations/{conversation_id}/plan",
            "/api/paper-agent/conversations/{conversation_id}/messages",
            "/api/paper-agent/conversations/{conversation_id}/status",
            "/api/paper-agent/conversations/{conversation_id}/{action}",
        }
        self.assertTrue(expected.issubset(paths))

    async def test_create_returns_traceable_conversation_id(self):
        with patch(
            "app.modules.paper_agent.conversation_router.create_conversation",
            new=AsyncMock(return_value=conversation()),
        ):
            response = await self.client.post(
                "/api/paper-agent/conversations",
                json={"conversation_id": "conv-api", "title": "细胞测试"},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["conversation_id"], "conv-api")

    async def test_submit_message_returns_all_execution_ids(self):
        with patch(
            "app.modules.paper_agent.conversation_router.submit_conversation_message",
            new=AsyncMock(return_value=graph_status()),
        ):
            response = await self.client.post(
                "/api/paper-agent/conversations/conv-api/messages",
                json={"message_id": "msg-api", "content": "组一份细胞试卷"},
            )

        self.assertEqual(response.status_code, 200)
        state = response.json()["state"]
        self.assertEqual(state["conversation_id"], "conv-api")
        self.assertEqual(state["message_id"], "msg-api")
        self.assertEqual(state["plan_version"], 1)
        self.assertEqual(state["pending_action_id"], "action-api")

    async def test_repeated_command_returns_uniform_conflict(self):
        with patch(
            "app.modules.paper_agent.conversation_router.command_conversation",
            new=AsyncMock(
                side_effect=ConversationGraphNotInterruptedError("completed")
            ),
        ):
            response = await self.client.post(
                "/api/paper-agent/conversations/conv-api/confirm"
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "ACTION_NOT_PENDING")
        self.assertFalse(response.json()["detail"]["retryable"])


if __name__ == "__main__":
    unittest.main()

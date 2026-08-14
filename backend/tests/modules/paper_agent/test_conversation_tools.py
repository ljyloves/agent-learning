import unittest
from unittest.mock import AsyncMock, Mock

from pydantic import ValidationError

from app.models import PendingActionModel
from app.modules.paper_agent.schemas.conversation import (
    PendingActionStatus,
    PendingActionType,
    ToolAccessMode,
)
from app.modules.paper_agent.schemas.tools import PrepareExportsToolOutput
from app.modules.paper_agent.schemas.tools import EmptyToolInput
from app.modules.paper_agent.services.conversation_tools import (
    ControlledToolExecutor,
    ToolConfirmationRequiredError,
    ToolContext,
    ToolDefinition,
    ToolNotAllowedError,
    ToolRegistry,
)


class ConversationToolTests(unittest.IsolatedAsyncioTestCase):
    def test_registry_exposes_only_named_allowlist(self):
        executor = ControlledToolExecutor()

        self.assertIn("create_paper", executor.registry.names)
        self.assertIn("preview_taxonomy_change", executor.registry.names)
        self.assertIn("apply_taxonomy_change", executor.registry.names)
        self.assertIn("deactivate_taxonomy_item", executor.registry.names)
        self.assertNotIn("execute_sql", executor.registry.names)
        self.assertNotIn("read_file", executor.registry.names)
        with self.assertRaises(ToolNotAllowedError):
            executor.registry.get("execute_sql")

    async def test_tool_input_rejects_unexpected_sql_field(self):
        context = ToolContext(
            session=AsyncMock(),
            review_graph=None,
            conversation_id="conv-1",
        )

        with self.assertRaises(ValidationError):
            await ControlledToolExecutor().execute(
                "search_questions",
                {"page": 1, "page_size": 20, "sql": "DROP TABLE questions"},
                context,
            )

    async def test_write_tool_requires_confirmed_action(self):
        handler = AsyncMock()
        definition = ToolDefinition(
            name="prepare_exports",
            action_type=PendingActionType.EXPORT_DOCUMENTS,
            access_mode=ToolAccessMode.WRITE,
            input_model=__import__(
                "app.modules.paper_agent.schemas.tools",
                fromlist=["PrepareExportsToolInput"],
            ).PrepareExportsToolInput,
            output_model=PrepareExportsToolOutput,
            handler=handler,
        )
        executor = ControlledToolExecutor(ToolRegistry([definition]))
        session = AsyncMock()
        context = ToolContext(session=session, review_graph=None, conversation_id="conv-1")

        with self.assertRaises(ToolConfirmationRequiredError):
            await executor.execute(
                "prepare_exports",
                {"job_id": "job-1"},
                context,
            )
        handler.assert_not_awaited()

    async def test_completed_action_id_returns_saved_result_without_reexecution(self):
        handler = AsyncMock()
        definition = ToolDefinition(
            name="prepare_exports",
            action_type=PendingActionType.EXPORT_DOCUMENTS,
            access_mode=ToolAccessMode.WRITE,
            input_model=__import__(
                "app.modules.paper_agent.schemas.tools",
                fromlist=["PrepareExportsToolInput"],
            ).PrepareExportsToolInput,
            output_model=PrepareExportsToolOutput,
            handler=handler,
        )
        executor = ControlledToolExecutor(ToolRegistry([definition]))
        saved = {
            "job_id": "job-1",
            "status": "completed",
            "review_status": "approved",
            "links": [
                {
                    "label": "all-documents",
                    "url": "/exports.zip",
                    "file_format": "zip",
                }
            ],
        }
        action = PendingActionModel(
            action_id="action-1",
            conversation_id="conv-1",
            action_type=PendingActionType.EXPORT_DOCUMENTS.value,
            status=PendingActionStatus.COMPLETED.value,
            request_payload={"job_id": "job-1"},
            result_payload=saved,
        )
        session = AsyncMock()
        session.add = Mock()
        session.scalar.return_value = action
        context = ToolContext(session=session, review_graph=None, conversation_id="conv-1")

        result = await executor.execute(
            "prepare_exports",
            {"job_id": "job-1"},
            context,
            action_id="action-1",
        )

        self.assertEqual(result, saved)
        handler.assert_not_awaited()

    async def test_confirmed_action_cannot_execute_different_payload(self):
        definition = ToolDefinition(
            name="prepare_exports",
            action_type=PendingActionType.EXPORT_DOCUMENTS,
            access_mode=ToolAccessMode.WRITE,
            input_model=__import__(
                "app.modules.paper_agent.schemas.tools",
                fromlist=["PrepareExportsToolInput"],
            ).PrepareExportsToolInput,
            output_model=PrepareExportsToolOutput,
            handler=AsyncMock(),
        )
        executor = ControlledToolExecutor(ToolRegistry([definition]))
        action = PendingActionModel(
            action_id="action-1",
            conversation_id="conv-1",
            action_type=PendingActionType.EXPORT_DOCUMENTS.value,
            status=PendingActionStatus.CONFIRMED.value,
            request_payload={"job_id": "job-original"},
        )
        session = AsyncMock()
        session.scalar.return_value = action
        context = ToolContext(session=session, review_graph=None, conversation_id="conv-1")

        with self.assertRaises(ToolConfirmationRequiredError):
            await executor.execute(
                "prepare_exports",
                {"job_id": "job-changed"},
                context,
                action_id="action-1",
            )

        definition.handler.assert_not_awaited()

    async def test_confirmed_action_executes_once_and_caches_result(self):
        saved = {
            "job_id": "job-1",
            "status": "completed",
            "review_status": "approved",
            "links": [
                {
                    "label": "all-documents",
                    "url": "/exports.zip",
                    "file_format": "zip",
                }
            ],
        }
        handler = AsyncMock(
            return_value=PrepareExportsToolOutput.model_validate(saved)
        )
        definition = ToolDefinition(
            name="prepare_exports",
            action_type=PendingActionType.EXPORT_DOCUMENTS,
            access_mode=ToolAccessMode.WRITE,
            input_model=__import__(
                "app.modules.paper_agent.schemas.tools",
                fromlist=["PrepareExportsToolInput"],
            ).PrepareExportsToolInput,
            output_model=PrepareExportsToolOutput,
            handler=handler,
        )
        executor = ControlledToolExecutor(ToolRegistry([definition]))
        action = PendingActionModel(
            action_id="action-1",
            conversation_id="conv-1",
            action_type=PendingActionType.EXPORT_DOCUMENTS.value,
            status=PendingActionStatus.CONFIRMED.value,
            request_payload={"job_id": "job-1"},
        )
        session = AsyncMock()
        session.add = Mock()
        session.scalar.return_value = action
        context = ToolContext(session=session, review_graph=None, conversation_id="conv-1")

        first = await executor.execute(
            "prepare_exports",
            {"job_id": "job-1"},
            context,
            action_id="action-1",
        )
        second = await executor.execute(
            "prepare_exports",
            {"job_id": "job-1"},
            context,
            action_id="action-1",
        )

        self.assertEqual(first, saved)
        self.assertEqual(second, saved)
        handler.assert_awaited_once()

    async def test_read_tool_retries_one_transient_timeout(self):
        handler = AsyncMock(
            side_effect=[TimeoutError("temporary"), EmptyToolInput()]
        )
        executor = ControlledToolExecutor(
            ToolRegistry(
                [
                    ToolDefinition(
                        name="health_probe",
                        action_type=None,
                        access_mode=ToolAccessMode.READ,
                        input_model=EmptyToolInput,
                        output_model=EmptyToolInput,
                        handler=handler,
                        timeout_seconds=1,
                    )
                ]
            )
        )
        session = AsyncMock()
        session.add = Mock()
        context = ToolContext(
            session=session,
            review_graph=None,
            conversation_id="conv-1",
        )

        result = await executor.execute("health_probe", {}, context)

        self.assertEqual(result, {})
        self.assertEqual(handler.await_count, 2)

    async def test_write_tool_never_retries_automatically(self):
        handler = AsyncMock(side_effect=TimeoutError("temporary"))
        definition = ToolDefinition(
            name="prepare_exports",
            action_type=PendingActionType.EXPORT_DOCUMENTS,
            access_mode=ToolAccessMode.WRITE,
            input_model=__import__(
                "app.modules.paper_agent.schemas.tools",
                fromlist=["PrepareExportsToolInput"],
            ).PrepareExportsToolInput,
            output_model=PrepareExportsToolOutput,
            handler=handler,
            timeout_seconds=1,
        )
        action = PendingActionModel(
            action_id="action-1",
            conversation_id="conv-1",
            action_type=PendingActionType.EXPORT_DOCUMENTS.value,
            status=PendingActionStatus.CONFIRMED.value,
            request_payload={"job_id": "job-1"},
        )
        execution = None
        session = AsyncMock()
        session.add = Mock(side_effect=lambda value: None)
        session.scalar.return_value = action
        session.get.side_effect = lambda model, _: action if model is PendingActionModel else execution
        context = ToolContext(session=session, review_graph=None, conversation_id="conv-1")

        with self.assertRaises(TimeoutError):
            await ControlledToolExecutor(ToolRegistry([definition])).execute(
                "prepare_exports",
                {"job_id": "job-1"},
                context,
                action_id="action-1",
            )

        handler.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

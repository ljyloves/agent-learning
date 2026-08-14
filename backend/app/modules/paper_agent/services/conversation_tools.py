"""Allowlisted, validated and audited tools for the conversational Agent."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PendingActionModel, ToolExecutionModel
from app.modules.paper_agent.schemas.conversation import (
    PendingActionStatus,
    PendingActionType,
    ToolAccessMode,
    ToolExecutionStatus,
)
from app.modules.paper_agent.schemas.library import (
    QuestionLibraryResponse,
    SourceLibraryResponse,
)
from app.modules.paper_agent.schemas.optimized_task import OptimizedPaperTaskResponse
from app.modules.paper_agent.schemas.taxonomy import BiologyTaxonomyResponse
from app.modules.paper_agent.schemas.taxonomy_change import (
    ApplyTaxonomyChangeToolInput,
    DeactivateTaxonomyItemToolInput,
    PreviewTaxonomyChangeToolInput,
    TaxonomyChangePreview,
    TaxonomyChangeResult,
)
from app.modules.paper_agent.schemas.tools import (
    CreatePaperToolInput,
    EmptyToolInput,
    GetPaperStatusToolInput,
    LockQuestionsToolInput,
    PrepareExportsToolInput,
    PrepareExportsToolOutput,
    ReassemblePaperToolInput,
    ReplaceQuestionToolInput,
    SearchQuestionsToolInput,
    SearchSourcesToolInput,
    SubmitReviewToolInput,
)
from app.modules.paper_agent.services.optimized_task import (
    create_optimized_task,
    get_optimized_task,
    reassemble_optimized_task,
    replace_optimized_question,
    review_optimized_task,
    update_optimized_task_locks,
)
from app.modules.paper_agent.services.source_library import (
    list_library_questions,
    list_sources,
)
from app.modules.paper_agent.services.taxonomy import get_biology_taxonomy
from app.modules.paper_agent.services.taxonomy_change import (
    apply_taxonomy_change,
    preview_taxonomy_change,
)


ToolHandler = Callable[["ToolContext", BaseModel], Awaitable[BaseModel]]


class ToolNotAllowedError(ValueError):
    pass


class ToolConfirmationRequiredError(PermissionError):
    pass


class ToolActionInProgressError(RuntimeError):
    pass


class ToolExecutionTimeoutError(TimeoutError):
    def __init__(self, message: str, *, attempt_count: int) -> None:
        super().__init__(message)
        self.attempt_count = attempt_count


@dataclass(frozen=True, slots=True)
class ToolContext:
    session: AsyncSession
    review_graph: Any
    conversation_id: str


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    action_type: PendingActionType | None
    access_mode: ToolAccessMode
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: ToolHandler
    timeout_seconds: float = 30.0


class ToolRegistry:
    def __init__(self, definitions: list[ToolDefinition]) -> None:
        names = [definition.name for definition in definitions]
        if len(names) != len(set(names)):
            raise ValueError("tool names must be unique")
        self._definitions = {definition.name: definition for definition in definitions}

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._definitions)

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise ToolNotAllowedError(f"tool is not allowlisted: {name}") from exc

    def schemas(self) -> dict[str, dict[str, Any]]:
        return {
            name: definition.input_model.model_json_schema()
            for name, definition in self._definitions.items()
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json_payload(value: BaseModel) -> dict[str, Any]:
    return value.model_dump(mode="json")


async def _query_taxonomy(
    context: ToolContext,
    _: EmptyToolInput,
) -> BiologyTaxonomyResponse:
    return await get_biology_taxonomy(context.session)


async def _preview_taxonomy_change(
    context: ToolContext,
    payload: PreviewTaxonomyChangeToolInput,
) -> TaxonomyChangePreview:
    return await preview_taxonomy_change(context.session, payload.change)


async def _apply_taxonomy_change(
    context: ToolContext,
    payload: ApplyTaxonomyChangeToolInput,
) -> TaxonomyChangeResult:
    return await apply_taxonomy_change(context.session, payload.change)


async def _deactivate_taxonomy_item(
    context: ToolContext,
    payload: DeactivateTaxonomyItemToolInput,
) -> TaxonomyChangeResult:
    return await apply_taxonomy_change(context.session, payload.to_change())


async def _search_questions(
    context: ToolContext,
    payload: SearchQuestionsToolInput,
) -> QuestionLibraryResponse:
    return await list_library_questions(context.session, **payload.model_dump())


async def _search_sources(
    context: ToolContext,
    payload: SearchSourcesToolInput,
) -> SourceLibraryResponse:
    return await list_sources(context.session, **payload.model_dump())


async def _get_paper_status(
    context: ToolContext,
    payload: GetPaperStatusToolInput,
) -> OptimizedPaperTaskResponse:
    return await get_optimized_task(context.session, payload.job_id)


async def _create_paper(
    context: ToolContext,
    payload: CreatePaperToolInput,
) -> OptimizedPaperTaskResponse:
    return await create_optimized_task(
        context.session,
        context.review_graph,
        payload.plan.to_task_create(),
    )


async def _lock_questions(
    context: ToolContext,
    payload: LockQuestionsToolInput,
) -> OptimizedPaperTaskResponse:
    return await update_optimized_task_locks(
        context.session,
        payload.job_id,
        payload.update,
    )


async def _replace_question(
    context: ToolContext,
    payload: ReplaceQuestionToolInput,
) -> OptimizedPaperTaskResponse:
    return await replace_optimized_question(
        context.session,
        context.review_graph,
        payload.job_id,
        payload.replacement,
    )


async def _reassemble_paper(
    context: ToolContext,
    payload: ReassemblePaperToolInput,
) -> OptimizedPaperTaskResponse:
    return await reassemble_optimized_task(
        context.session,
        context.review_graph,
        payload.job_id,
        payload.request,
    )


async def _submit_review(
    context: ToolContext,
    payload: SubmitReviewToolInput,
) -> OptimizedPaperTaskResponse:
    return await review_optimized_task(
        context.session,
        context.review_graph,
        payload.job_id,
        payload.review,
    )


async def _prepare_exports(
    context: ToolContext,
    payload: PrepareExportsToolInput,
) -> PrepareExportsToolOutput:
    task = await get_optimized_task(context.session, payload.job_id)
    base = f"/api/paper-agent/optimized-tasks/{payload.job_id}"
    links = [
        {
            "label": f"{document}-{file_format}",
            "url": f"{base}/exports/{document}/{file_format}",
            "file_format": file_format,
        }
        for document in ("student", "teacher-answer", "answer-sheet")
        for file_format in ("docx", "pdf")
    ]
    links.append(
        {
            "label": "all-documents",
            "url": f"{base}/exports.zip",
            "file_format": "zip",
        }
    )
    return PrepareExportsToolOutput(
        job_id=payload.job_id,
        status=task.status,
        review_status=task.review_status,
        links=links,
    )


DEFAULT_TOOL_REGISTRY = ToolRegistry(
    [
        ToolDefinition("query_taxonomy", None, ToolAccessMode.READ, EmptyToolInput, BiologyTaxonomyResponse, _query_taxonomy),
        ToolDefinition("preview_taxonomy_change", None, ToolAccessMode.READ, PreviewTaxonomyChangeToolInput, TaxonomyChangePreview, _preview_taxonomy_change),
        ToolDefinition("apply_taxonomy_change", PendingActionType.APPLY_TAXONOMY_CHANGE, ToolAccessMode.WRITE, ApplyTaxonomyChangeToolInput, TaxonomyChangeResult, _apply_taxonomy_change),
        ToolDefinition("deactivate_taxonomy_item", PendingActionType.DEACTIVATE_TAXONOMY_ITEM, ToolAccessMode.WRITE, DeactivateTaxonomyItemToolInput, TaxonomyChangeResult, _deactivate_taxonomy_item),
        ToolDefinition("search_questions", None, ToolAccessMode.READ, SearchQuestionsToolInput, QuestionLibraryResponse, _search_questions),
        ToolDefinition("search_sources", None, ToolAccessMode.READ, SearchSourcesToolInput, SourceLibraryResponse, _search_sources),
        ToolDefinition("get_paper_status", None, ToolAccessMode.READ, GetPaperStatusToolInput, OptimizedPaperTaskResponse, _get_paper_status),
        ToolDefinition("create_paper", PendingActionType.CREATE_PAPER, ToolAccessMode.WRITE, CreatePaperToolInput, OptimizedPaperTaskResponse, _create_paper),
        ToolDefinition("lock_questions", PendingActionType.LOCK_QUESTIONS, ToolAccessMode.WRITE, LockQuestionsToolInput, OptimizedPaperTaskResponse, _lock_questions),
        ToolDefinition("replace_question", PendingActionType.REPLACE_QUESTION, ToolAccessMode.WRITE, ReplaceQuestionToolInput, OptimizedPaperTaskResponse, _replace_question),
        ToolDefinition("reassemble_paper", PendingActionType.REASSEMBLE_PAPER, ToolAccessMode.WRITE, ReassemblePaperToolInput, OptimizedPaperTaskResponse, _reassemble_paper),
        ToolDefinition("submit_review", PendingActionType.SUBMIT_REVIEW, ToolAccessMode.WRITE, SubmitReviewToolInput, OptimizedPaperTaskResponse, _submit_review),
        ToolDefinition("prepare_exports", PendingActionType.EXPORT_DOCUMENTS, ToolAccessMode.WRITE, PrepareExportsToolInput, PrepareExportsToolOutput, _prepare_exports),
    ]
)


class ControlledToolExecutor:
    def __init__(self, registry: ToolRegistry = DEFAULT_TOOL_REGISTRY) -> None:
        self.registry = registry

    async def execute(
        self,
        name: str,
        payload: dict[str, Any],
        context: ToolContext,
        *,
        action_id: str | None = None,
    ) -> dict[str, Any]:
        definition = self.registry.get(name)
        validated_input = definition.input_model.model_validate(payload)
        if definition.access_mode == ToolAccessMode.WRITE:
            return await self._execute_write(
                definition,
                validated_input,
                context,
                action_id=action_id,
            )
        return await self._execute_read(definition, validated_input, context)

    async def _run(
        self,
        definition: ToolDefinition,
        validated_input: BaseModel,
        context: ToolContext,
    ) -> tuple[BaseModel, int]:
        timeout = min(
            definition.timeout_seconds,
            settings.paper_agent_tool_timeout_seconds,
        )
        max_attempts = 1 + (
            settings.paper_agent_tool_read_retry_count
            if definition.access_mode == ToolAccessMode.READ
            else 0
        )
        for attempt in range(1, max_attempts + 1):
            try:
                result = await asyncio.wait_for(
                    definition.handler(context, validated_input),
                    timeout=timeout,
                )
                return definition.output_model.model_validate(result), attempt
            except TimeoutError as exc:
                if attempt < max_attempts:
                    continue
                raise ToolExecutionTimeoutError(
                    f"tool timed out after {timeout:g} seconds: {definition.name}",
                    attempt_count=attempt,
                ) from exc
            except ConnectionError as exc:
                if attempt < max_attempts:
                    continue
                setattr(exc, "tool_attempt_count", attempt)
                raise
        raise RuntimeError("tool retry loop ended without a result")

    async def _execute_read(
        self,
        definition: ToolDefinition,
        validated_input: BaseModel,
        context: ToolContext,
    ) -> dict[str, Any]:
        execution = ToolExecutionModel(
            execution_id=str(uuid.uuid4()),
            conversation_id=context.conversation_id,
            action_id=None,
            tool_name=definition.name,
            access_mode=definition.access_mode.value,
            status=ToolExecutionStatus.STARTED.value,
            request_payload=_json_payload(validated_input),
        )
        context.session.add(execution)
        try:
            result, attempt_count = await self._run(
                definition,
                validated_input,
                context,
            )
            execution.attempt_count = attempt_count
            execution.status = ToolExecutionStatus.SUCCEEDED.value
            execution.result_payload = _json_payload(result)
            execution.completed_at = _now()
            await context.session.commit()
            return execution.result_payload
        except Exception as exc:
            await context.session.rollback()
            failed = ToolExecutionModel(
                execution_id=execution.execution_id,
                conversation_id=context.conversation_id,
                action_id=None,
                tool_name=definition.name,
                access_mode=definition.access_mode.value,
                status=(
                    ToolExecutionStatus.TIMED_OUT.value
                    if isinstance(exc, ToolExecutionTimeoutError)
                    else ToolExecutionStatus.FAILED.value
                ),
                attempt_count=getattr(
                    exc,
                    "attempt_count",
                    getattr(exc, "tool_attempt_count", 1),
                ),
                request_payload=_json_payload(validated_input),
                error_code=type(exc).__name__,
                error_message=str(exc)[:2000],
                completed_at=_now(),
            )
            context.session.add(failed)
            await context.session.commit()
            raise

    async def _execute_write(
        self,
        definition: ToolDefinition,
        validated_input: BaseModel,
        context: ToolContext,
        *,
        action_id: str | None,
    ) -> dict[str, Any]:
        if action_id is None:
            raise ToolConfirmationRequiredError("write tool requires action_id")
        action = await context.session.scalar(
            select(PendingActionModel)
            .where(PendingActionModel.action_id == action_id)
            .with_for_update()
        )
        if action is None or action.conversation_id != context.conversation_id:
            raise ToolConfirmationRequiredError("confirmed action was not found")
        if action.action_type != definition.action_type.value:
            raise ToolConfirmationRequiredError("action does not match tool")
        if action.request_payload != _json_payload(validated_input):
            raise ToolConfirmationRequiredError(
                "confirmed action payload does not match tool input"
            )
        if action.status == PendingActionStatus.COMPLETED.value:
            return definition.output_model.model_validate(
                action.result_payload
            ).model_dump(mode="json")
        if action.status == PendingActionStatus.EXECUTING.value:
            raise ToolActionInProgressError(action_id)
        if action.status != PendingActionStatus.CONFIRMED.value:
            raise ToolConfirmationRequiredError(
                f"action is not confirmed: {action.status}"
            )

        execution = ToolExecutionModel(
            execution_id=str(uuid.uuid4()),
            conversation_id=context.conversation_id,
            action_id=action_id,
            tool_name=definition.name,
            access_mode=definition.access_mode.value,
            status=ToolExecutionStatus.STARTED.value,
            request_payload=_json_payload(validated_input),
        )
        action.status = PendingActionStatus.EXECUTING.value
        context.session.add(execution)
        await context.session.commit()
        try:
            result, attempt_count = await self._run(
                definition,
                validated_input,
                context,
            )
            execution.attempt_count = attempt_count
            result_payload = _json_payload(result)
            action.status = PendingActionStatus.COMPLETED.value
            action.result_payload = result_payload
            action.completed_at = _now()
            action.updated_at = _now()
            action.paper_job_id = result_payload.get("job_id")
            execution.status = ToolExecutionStatus.SUCCEEDED.value
            execution.result_payload = result_payload
            execution.completed_at = _now()
            await context.session.commit()
            return result_payload
        except Exception as exc:
            await context.session.rollback()
            action = await context.session.get(PendingActionModel, action_id)
            execution = await context.session.get(
                ToolExecutionModel,
                execution.execution_id,
            )
            if action is not None:
                action.status = PendingActionStatus.FAILED.value
                action.error_code = type(exc).__name__
                action.error_message = str(exc)[:2000]
                action.completed_at = _now()
                action.updated_at = _now()
            if execution is not None:
                execution.status = (
                    ToolExecutionStatus.TIMED_OUT.value
                    if isinstance(exc, ToolExecutionTimeoutError)
                    else ToolExecutionStatus.FAILED.value
                )
                execution.error_code = type(exc).__name__
                execution.error_message = str(exc)[:2000]
                execution.completed_at = _now()
            await context.session.commit()
            raise


controlled_tool_executor = ControlledToolExecutor()


__all__ = [
    "ControlledToolExecutor",
    "DEFAULT_TOOL_REGISTRY",
    "ToolActionInProgressError",
    "ToolConfirmationRequiredError",
    "ToolContext",
    "ToolDefinition",
    "ToolExecutionTimeoutError",
    "ToolNotAllowedError",
    "ToolRegistry",
    "controlled_tool_executor",
]

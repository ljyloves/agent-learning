"""Initialization node and its explicit Pydantic contract."""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.paper_agent.graph.contracts import (
    GraphNodeContract,
    validated_node,
)
from app.modules.paper_agent.graph.state import (
    Identifier,
    PaperGraphExecution,
    PaperGraphReport,
    PaperGraphState,
)
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus


class InitializeNodeInput(BaseModel):
    """Validated state snapshot consumed by the initialization node."""

    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    candidate_question_ids: list[Identifier] = Field(max_length=1000)
    selected_question_ids: list[Identifier] = Field(max_length=1000)
    reports: list[PaperGraphReport] = Field(max_length=200)
    execution: PaperGraphExecution


class InitializeNodeOutput(BaseModel):
    """Validated partial state update emitted by the initialization node."""

    model_config = ConfigDict(extra="forbid")

    reports: list[PaperGraphReport] = Field(max_length=200)
    execution: PaperGraphExecution


INITIALIZE_NODE_CONTRACT = GraphNodeContract(
    name="initialize",
    state_model=PaperGraphState,
    input_model=InitializeNodeInput,
    output_model=InitializeNodeOutput,
)


@validated_node(INITIALIZE_NODE_CONTRACT)
def initialize_paper_agent(state: InitializeNodeInput) -> InitializeNodeOutput:
    attempt = state.execution.attempt + 1
    report = PaperGraphReport(
        report_id=f"initialize:{attempt}",
        stage="initialize",
        summary="Paper graph state initialized.",
        metrics={
            "candidate_question_count": len(state.candidate_question_ids),
            "selected_question_count": len(state.selected_question_ids),
        },
    )
    execution = PaperGraphExecution(
        status=PaperJobStatus.RUNNING,
        current_node="initialize",
        attempt=attempt,
        retry_count=state.execution.retry_count,
        replacement_count=state.execution.replacement_count,
    )
    return InitializeNodeOutput(
        reports=[*state.reports, report],
        execution=execution,
    )

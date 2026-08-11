"""LangGraph workflow definitions for paper generation."""

from app.modules.paper_agent.graph.contracts import (
    GraphNodeContract,
    add_contract_node,
    get_node_contract,
    validated_node,
)
from app.modules.paper_agent.graph.state import (
    PaperGraphDecision,
    PaperGraphExecution,
    PaperGraphReport,
    PaperGraphReportLevel,
    PaperGraphState,
)
from app.modules.paper_agent.graph.workflow import (
    build_paper_agent_graph,
    build_teacher_review_graph,
    paper_agent_graph,
    select_workflow_branch,
    select_teacher_review_branch,
)
from app.modules.paper_agent.nodes import (
    INITIALIZE_NODE_CONTRACT,
    MAIN_WORKFLOW_NODES,
    MAX_RETRY_ATTEMPTS,
    InitializeNodeInput,
    InitializeNodeOutput,
    initialize_paper_agent,
)

__all__ = [
    "GraphNodeContract",
    "INITIALIZE_NODE_CONTRACT",
    "InitializeNodeInput",
    "InitializeNodeOutput",
    "MAIN_WORKFLOW_NODES",
    "MAX_RETRY_ATTEMPTS",
    "PaperGraphDecision",
    "PaperGraphExecution",
    "PaperGraphReport",
    "PaperGraphReportLevel",
    "PaperGraphState",
    "add_contract_node",
    "build_paper_agent_graph",
    "build_teacher_review_graph",
    "get_node_contract",
    "initialize_paper_agent",
    "paper_agent_graph",
    "select_workflow_branch",
    "select_teacher_review_branch",
    "validated_node",
]

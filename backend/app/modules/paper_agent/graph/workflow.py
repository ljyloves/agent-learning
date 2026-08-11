from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.modules.paper_agent.graph.contracts import add_contract_node
from app.modules.paper_agent.graph.state import PaperGraphDecision, PaperGraphState
from app.modules.paper_agent.nodes import (
    MAX_RETRY_ATTEMPTS,
    complete_workflow,
    decide_workflow,
    fail_workflow,
    initialize_paper_agent,
    queue_workflow_retry,
    replace_question,
    await_teacher_review,
    queue_teacher_review,
)


def select_workflow_branch(state: PaperGraphState) -> str:
    validated_state = PaperGraphState.model_validate(state)
    decision = validated_state.execution.decision
    if decision is None:
        raise ValueError("workflow decision is required before routing")
    if (
        decision == PaperGraphDecision.RETRY
        and validated_state.execution.retry_count >= MAX_RETRY_ATTEMPTS
    ):
        return PaperGraphDecision.FAIL.value
    return decision.value


def build_paper_agent_graph(
    checkpointer: BaseCheckpointSaver | None = None,
):
    graph = StateGraph(PaperGraphState)
    initialize_node = add_contract_node(graph, initialize_paper_agent)
    decide_node = add_contract_node(graph, decide_workflow)
    complete_node = add_contract_node(graph, complete_workflow)
    fail_node = add_contract_node(graph, fail_workflow)
    retry_node = add_contract_node(graph, queue_workflow_retry)
    replace_node = add_contract_node(graph, replace_question)

    graph.add_edge(START, initialize_node)
    graph.add_edge(initialize_node, decide_node)
    graph.add_conditional_edges(
        decide_node,
        select_workflow_branch,
        {
            PaperGraphDecision.PASS.value: complete_node,
            PaperGraphDecision.FAIL.value: fail_node,
            PaperGraphDecision.RETRY.value: retry_node,
            PaperGraphDecision.REPLACE.value: replace_node,
        },
    )
    for terminal_node in (complete_node, fail_node, retry_node, replace_node):
        graph.add_edge(terminal_node, END)
    return graph.compile(checkpointer=checkpointer)


def select_teacher_review_branch(state: PaperGraphState) -> str:
    validated_state = PaperGraphState.model_validate(state)
    decision = validated_state.execution.decision
    supported_decisions = {
        PaperGraphDecision.PASS,
        PaperGraphDecision.FAIL,
        PaperGraphDecision.REPLACE,
    }
    if decision not in supported_decisions:
        raise ValueError("teacher review requires approve, reject, or replace")
    return decision.value


def build_teacher_review_graph(checkpointer: BaseCheckpointSaver):
    graph = StateGraph(PaperGraphState)
    initialize_node = add_contract_node(graph, initialize_paper_agent)
    queue_review_node = add_contract_node(graph, queue_teacher_review)
    await_review_node = add_contract_node(graph, await_teacher_review)
    complete_node = add_contract_node(graph, complete_workflow)
    fail_node = add_contract_node(graph, fail_workflow)
    replace_node = add_contract_node(graph, replace_question)

    graph.add_edge(START, initialize_node)
    graph.add_edge(initialize_node, queue_review_node)
    graph.add_edge(queue_review_node, await_review_node)
    graph.add_conditional_edges(
        await_review_node,
        select_teacher_review_branch,
        {
            PaperGraphDecision.PASS.value: complete_node,
            PaperGraphDecision.FAIL.value: fail_node,
            PaperGraphDecision.REPLACE.value: replace_node,
        },
    )
    graph.add_edge(replace_node, queue_review_node)
    graph.add_edge(complete_node, END)
    graph.add_edge(fail_node, END)
    return graph.compile(checkpointer=checkpointer)


paper_agent_graph = build_paper_agent_graph()

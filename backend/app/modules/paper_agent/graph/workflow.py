from langgraph.graph import END, START, StateGraph

from app.modules.paper_agent.graph.state import PaperAgentState


def initialize_paper_agent(state: PaperAgentState) -> dict:
    return {
        "status": "ready",
        "steps": [*state["steps"], "initialize"],
    }


def build_paper_agent_graph():
    graph = StateGraph(PaperAgentState)
    graph.add_node("initialize", initialize_paper_agent)
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", END)
    return graph.compile()


paper_agent_graph = build_paper_agent_graph()

# 定义全局状态
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages # type: ignore

#全局状态
class SearchState(TypedDict):
    messages: Annotated[list, add_messages]
    user_query: str
    search_query: str
    search_results: list
    final_answer: str
    step: str
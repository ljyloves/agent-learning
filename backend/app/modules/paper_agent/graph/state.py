from typing import TypedDict


class PaperAgentState(TypedDict):
    job_id: str
    status: str
    steps: list[str]

"""Teacher resource library and question-bank list contracts."""

from enum import Enum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.modules.paper_agent.graph.state import Identifier
from app.modules.paper_agent.schemas.question import QuestionDifficulty, QuestionType
from app.modules.paper_agent.schemas.source import ResourceType, SourceType


class SourceProcessingStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceLibraryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: Identifier
    resource_id: Identifier | None = None
    name: str
    source_type: SourceType
    resource_type: ResourceType | None = None
    mime_type: str | None = None
    locator: str | None = None
    attribution: str | None = None
    retrieved_at: AwareDatetime
    processing_status: SourceProcessingStatus
    failure_reason: str | None = None
    processed_at: AwareDatetime | None = None
    question_count: int = Field(ge=0)
    can_parse: bool


class SourceLibraryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SourceLibraryItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)


class QuestionLibraryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Identifier
    question_type: QuestionType
    difficulty: QuestionDifficulty
    stem: str
    has_answer: bool
    created_at: AwareDatetime
    source_id: Identifier
    source_name: str
    source_type: SourceType
    source_locator: str | None = None
    attribution: str | None = None


class QuestionLibraryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[QuestionLibraryItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)

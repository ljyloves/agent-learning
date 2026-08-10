"""Source and resource provenance schemas for paper questions."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256Digest = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        pattern=r"^[0-9a-fA-F]{64}$",
    ),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceType(str, Enum):
    WEBSITE = "website"
    API = "api"
    FILE = "file"
    BOOK = "book"
    MANUAL = "manual"


class ResourceType(str, Enum):
    IMAGE = "image"
    DOCUMENT = "document"
    WEBPAGE = "webpage"
    ATTACHMENT = "attachment"


class QuestionSource(BaseModel):
    """The original location from which a question or resource was obtained."""

    model_config = ConfigDict(extra="forbid")

    source_id: NonEmptyText
    source_type: SourceType
    name: NonEmptyText
    uri: NonEmptyText | None = None
    external_id: NonEmptyText | None = None
    retrieved_at: AwareDatetime = Field(default_factory=utc_now)
    attribution: NonEmptyText | None = None
    license: NonEmptyText | None = None

    @model_validator(mode="after")
    def require_locator(self) -> QuestionSource:
        if self.uri is None and self.external_id is None:
            raise ValueError("a source must define uri or external_id")
        return self


class QuestionResource(BaseModel):
    """A traceable asset associated with a question."""

    model_config = ConfigDict(extra="forbid")

    resource_id: NonEmptyText
    resource_type: ResourceType
    uri: NonEmptyText
    source: QuestionSource
    mime_type: NonEmptyText | None = None
    sha256: Sha256Digest | None = None

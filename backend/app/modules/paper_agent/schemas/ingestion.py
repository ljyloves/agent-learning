"""Contracts for traceable teacher file and website ingestion."""

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.modules.paper_agent.graph.state import Identifier
from app.modules.paper_agent.schemas.source import ResourceType, SourceType


class WebPageCollectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl


class IngestedResourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: Identifier
    resource_id: Identifier
    source_type: SourceType
    resource_type: ResourceType
    original_name: str | None = None
    source_url: HttpUrl | None = None
    storage_uri: str
    mime_type: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    title: str | None = None
    adapter: str | None = None

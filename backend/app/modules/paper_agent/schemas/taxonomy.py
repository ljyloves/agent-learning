"""API schemas for the biology taxonomy and persistence milestone."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.paper_agent.schemas.paper_job import PaperJob
from app.modules.paper_agent.schemas.question import Question


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
CodeList = Annotated[list[NonEmptyText], Field(min_length=1)]


class KnowledgePointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    description: str
    sort_order: int


class CurriculumModuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    course_type: str
    description: str
    sort_order: int
    knowledge_points: list[KnowledgePointRead]


class CoreCompetencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    description: str
    sort_order: int


class BiologyTaxonomyResponse(BaseModel):
    modules: list[CurriculumModuleRead]
    core_competencies: list[CoreCompetencyRead]


class PaperJobQuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job: PaperJob
    question: Question
    knowledge_point_codes: CodeList
    core_competency_codes: CodeList

    @field_validator("knowledge_point_codes", "core_competency_codes")
    @classmethod
    def require_unique_codes(cls, codes: list[str]) -> list[str]:
        if len(codes) != len(set(codes)):
            raise ValueError("taxonomy codes must be unique")
        return codes


class PaperJobQuestionCreated(BaseModel):
    job_id: str
    question_id: str
    job_status: str
    knowledge_point_codes: list[str]
    core_competency_codes: list[str]

"""Pydantic schemas for paper generation."""

from app.modules.paper_agent.schemas.paper_job import (
    PaperJob,
    PaperJobStatus,
    ReviewResult,
    ReviewStatus,
)
from app.modules.paper_agent.schemas.question import (
    Question,
    QuestionDifficulty,
    QuestionImage,
    QuestionOption,
    QuestionType,
)
from app.modules.paper_agent.schemas.source import (
    QuestionResource,
    QuestionSource,
    ResourceType,
    SourceType,
)
from app.modules.paper_agent.schemas.taxonomy import (
    BiologyTaxonomyResponse,
    CoreCompetencyRead,
    CurriculumModuleRead,
    KnowledgePointRead,
    PaperJobQuestionCreate,
    PaperJobQuestionCreated,
)

__all__ = [
    "BiologyTaxonomyResponse",
    "CoreCompetencyRead",
    "CurriculumModuleRead",
    "KnowledgePointRead",
    "PaperJob",
    "PaperJobQuestionCreate",
    "PaperJobQuestionCreated",
    "PaperJobStatus",
    "Question",
    "QuestionDifficulty",
    "QuestionImage",
    "QuestionOption",
    "QuestionResource",
    "QuestionSource",
    "QuestionType",
    "ResourceType",
    "ReviewResult",
    "ReviewStatus",
    "SourceType",
]

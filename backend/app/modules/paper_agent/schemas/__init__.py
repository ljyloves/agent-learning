"""Pydantic schemas for paper generation."""

from app.modules.paper_agent.schemas.annotation import (
    TaxonomyAnnotationLLMOutput,
    TaxonomyAnnotationRequest,
    TaxonomyAnnotationResponse,
)
from app.modules.paper_agent.schemas.analysis import (
    DifficultyEstimationResponse,
    QualityIssue,
    QualityIssueType,
    QualityReviewResponse,
    QualitySeverity,
)
from app.modules.paper_agent.schemas.optimization import (
    ConstraintAudit,
    CoverageConstraint,
    DifficultyQuota,
    DiversityConstraint,
    KnowledgePointTarget,
    OptimizedPaperRequest,
    OptimizedPaperResult,
)
from app.modules.paper_agent.schemas.optimized_task import (
    OptimizedPaperLockUpdate,
    OptimizedPaperReassemble,
    OptimizedPaperReplace,
    OptimizedPaperTaskCreate,
    OptimizedPaperTaskResponse,
    OptimizedPaperTaskReview,
)

from app.modules.paper_agent.schemas.paper_job import (
    PaperJob,
    PaperJobStatus,
    ReviewResult,
    ReviewStatus,
)
from app.modules.paper_agent.schemas.parsing import (
    ParsedQuestionsResponse,
    QuestionParseRequest,
)
from app.modules.paper_agent.schemas.question import (
    Question,
    QuestionDifficulty,
    QuestionImage,
    QuestionOption,
    QuestionType,
)
from app.modules.paper_agent.schemas.retrieval import (
    HybridQuestionCandidate,
    HybridQuestionSearchRequest,
    HybridQuestionSearchResponse,
    QuestionIndexRequest,
    QuestionIndexResponse,
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
    "ConstraintAudit",
    "CoverageConstraint",
    "CurriculumModuleRead",
    "DifficultyQuota",
    "DifficultyEstimationResponse",
    "DiversityConstraint",
    "KnowledgePointRead",
    "KnowledgePointTarget",
    "HybridQuestionCandidate",
    "HybridQuestionSearchRequest",
    "HybridQuestionSearchResponse",
    "PaperJob",
    "PaperJobQuestionCreate",
    "PaperJobQuestionCreated",
    "PaperJobStatus",
    "OptimizedPaperRequest",
    "OptimizedPaperResult",
    "OptimizedPaperLockUpdate",
    "OptimizedPaperReassemble",
    "OptimizedPaperReplace",
    "OptimizedPaperTaskCreate",
    "OptimizedPaperTaskResponse",
    "OptimizedPaperTaskReview",
    "ParsedQuestionsResponse",
    "Question",
    "QuestionDifficulty",
    "QuestionImage",
    "QuestionIndexRequest",
    "QuestionIndexResponse",
    "QuestionOption",
    "QuestionParseRequest",
    "QuestionResource",
    "QuestionSource",
    "QuestionType",
    "QualityIssue",
    "QualityIssueType",
    "QualityReviewResponse",
    "QualitySeverity",
    "ResourceType",
    "ReviewResult",
    "ReviewStatus",
    "SourceType",
    "TaxonomyAnnotationLLMOutput",
    "TaxonomyAnnotationRequest",
    "TaxonomyAnnotationResponse",
]

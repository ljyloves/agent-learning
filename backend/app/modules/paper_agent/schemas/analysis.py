"""Contracts for question difficulty estimation and quality review."""

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


Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
LocationText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]


class QuestionAnalysisType(str, Enum):
    DIFFICULTY_ESTIMATION = "difficulty_estimation"
    QUALITY_REVIEW = "quality_review"


class DifficultyEstimationLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    difficulty_level: int = Field(ge=1, le=5)
    estimated_correct_rate: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: ShortText

    @model_validator(mode="after")
    def require_consistent_level_and_rate(self) -> "DifficultyEstimationLLMOutput":
        expected_ranges = {
            1: (0.70, 1.00),
            2: (0.55, 0.90),
            3: (0.35, 0.75),
            4: (0.15, 0.55),
            5: (0.00, 0.35),
        }
        lower, upper = expected_ranges[self.difficulty_level]
        if not lower <= self.estimated_correct_rate <= upper:
            raise ValueError(
                "estimated_correct_rate is inconsistent with difficulty_level"
            )
        return self


class DifficultyEstimationResponse(DifficultyEstimationLLMOutput):
    analysis_id: Identifier
    question_id: Identifier
    model: str = Field(min_length=1, max_length=255)
    created_at: AwareDatetime


class QualityIssueType(str, Enum):
    MISSING_IMAGE = "missing_image"
    MISSING_ANSWER = "missing_answer"
    AMBIGUITY = "ambiguity"
    OUT_OF_SCOPE = "out_of_scope"


class QualitySeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class QualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: QualityIssueType
    severity: QualitySeverity
    location: LocationText
    description: ShortText
    suggestion: ShortText
    confidence: float = Field(ge=0.0, le=1.0)


class QualityReviewLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[QualityIssue] = Field(default_factory=list, max_length=20)
    summary: ShortText

    @model_validator(mode="after")
    def require_unique_issues(self) -> "QualityReviewLLMOutput":
        identities = [
            (issue.issue_type, issue.location.casefold())
            for issue in self.issues
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("quality issues must be unique by type and location")
        return self


class QualityReviewResponse(QualityReviewLLMOutput):
    analysis_id: Identifier
    question_id: Identifier
    model: str = Field(min_length=1, max_length=255)
    passed: bool
    created_at: AwareDatetime

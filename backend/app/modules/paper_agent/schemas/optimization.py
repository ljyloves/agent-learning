"""Contracts for auditable multi-constraint paper optimization."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.paper_agent.schemas.question import QuestionType


Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]


class DifficultyQuota(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_type: QuestionType
    difficulty_level: int = Field(ge=1, le=5)
    count: int = Field(ge=1, le=1000)
    score_per_question: int = Field(ge=1, le=100)

    @property
    def total_score(self) -> int:
        return self.count * self.score_per_question


class KnowledgePointTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Identifier
    minimum_count: int = Field(default=1, ge=0, le=1000)


class CoverageConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[KnowledgePointTarget] = Field(min_length=1, max_length=32)
    minimum_coverage_rate: float = Field(default=1.0, gt=0.0, le=1.0)

    @field_validator("targets")
    @classmethod
    def require_unique_targets(
        cls,
        values: list[KnowledgePointTarget],
    ) -> list[KnowledgePointTarget]:
        codes = [target.code for target in values]
        if len(codes) != len(set(codes)):
            raise ValueError("coverage target codes must be unique")
        return values


class DiversityConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_distinct_knowledge_points: int = Field(default=1, ge=1, le=32)
    minimum_distinct_core_competencies: int = Field(default=1, ge=1, le=4)
    minimum_distinct_sources: int = Field(default=1, ge=1, le=1000)
    maximum_questions_per_knowledge_point: int | None = Field(
        default=None,
        ge=1,
        le=1000,
    )
    maximum_questions_per_source: int | None = Field(
        default=None,
        ge=1,
        le=1000,
    )
    semantic_similarity_threshold: float = Field(default=0.94, ge=0.80, le=1.0)


class OptimizedPaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_code: Identifier = "BIO-M1"
    question_count: int = Field(ge=1, le=1000)
    total_score: int = Field(ge=1, le=10000)
    difficulty_quotas: list[DifficultyQuota] = Field(min_length=1, max_length=50)
    coverage: CoverageConstraint
    diversity: DiversityConstraint = Field(default_factory=DiversityConstraint)
    exclude_question_ids: list[Identifier] = Field(
        default_factory=list,
        max_length=1000,
    )
    random_seed: int = Field(default=0, ge=0, le=2_147_483_647)

    @field_validator("exclude_question_ids")
    @classmethod
    def require_unique_exclusions(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("exclude_question_ids must be unique")
        return values

    @model_validator(mode="after")
    def validate_constraints(self) -> "OptimizedPaperRequest":
        quota_keys = [
            (quota.question_type, quota.difficulty_level)
            for quota in self.difficulty_quotas
        ]
        if len(quota_keys) != len(set(quota_keys)):
            raise ValueError("question type and difficulty quotas must be unique")
        if sum(quota.count for quota in self.difficulty_quotas) != self.question_count:
            raise ValueError("question_count must equal the sum of quota counts")
        if sum(quota.total_score for quota in self.difficulty_quotas) != self.total_score:
            raise ValueError("total_score must equal the sum of quota scores")
        if any(
            target.minimum_count > self.question_count
            for target in self.coverage.targets
        ):
            raise ValueError("knowledge point minimum_count exceeds question_count")
        diversity_minima = (
            self.diversity.minimum_distinct_knowledge_points,
            self.diversity.minimum_distinct_core_competencies,
            self.diversity.minimum_distinct_sources,
        )
        if any(minimum > self.question_count for minimum in diversity_minima):
            raise ValueError("diversity minimum exceeds question_count")
        return self


class OptimizedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Identifier
    question_type: QuestionType
    difficulty_level: int = Field(ge=1, le=5)
    estimated_correct_rate: float = Field(ge=0.0, le=1.0)
    score: int = Field(ge=1, le=100)
    source_id: Identifier
    knowledge_point_codes: list[Identifier] = Field(min_length=1, max_length=32)
    core_competency_codes: list[Identifier] = Field(min_length=1, max_length=4)
    difficulty_analysis_id: Identifier
    quality_analysis_id: Identifier


class OptimizedSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_index: int = Field(ge=0)
    question_type: QuestionType
    difficulty_level: int = Field(ge=1, le=5)
    count: int = Field(ge=1, le=1000)
    score_per_question: int = Field(ge=1, le=100)
    questions: list[OptimizedQuestion] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_section(self) -> "OptimizedSection":
        if len(self.questions) != self.count:
            raise ValueError("optimized section count does not match questions")
        for question in self.questions:
            if question.question_type != self.question_type:
                raise ValueError("optimized question type does not match section")
            if question.difficulty_level != self.difficulty_level:
                raise ValueError("optimized question difficulty does not match section")
            if question.score != self.score_per_question:
                raise ValueError("optimized question score does not match section")
        return self


class ConstraintAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    satisfied: bool
    coverage_rate: float = Field(ge=0.0, le=1.0)
    target_knowledge_point_codes: list[Identifier]
    covered_knowledge_point_codes: list[Identifier]
    missing_knowledge_point_codes: list[Identifier]
    distinct_knowledge_point_count: int = Field(ge=0)
    distinct_core_competency_count: int = Field(ge=0)
    distinct_source_count: int = Field(ge=0)
    quality_approved_count: int = Field(ge=0)
    selected_duplicate_pair_count: int = Field(ge=0)


class OptimizedPaperResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_code: Identifier
    question_count: int = Field(ge=1, le=1000)
    total_score: int = Field(ge=1, le=10000)
    sections: list[OptimizedSection] = Field(min_length=1, max_length=50)
    audit: ConstraintAudit

    @model_validator(mode="after")
    def validate_result(self) -> "OptimizedPaperResult":
        questions = [
            question
            for section in self.sections
            for question in section.questions
        ]
        if len(questions) != self.question_count:
            raise ValueError("optimized paper question count does not match")
        question_ids = [question.question_id for question in questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("optimized paper question IDs must be unique")
        if sum(question.score for question in questions) != self.total_score:
            raise ValueError("optimized paper total score does not match")
        if not self.audit.satisfied:
            raise ValueError("optimized result must satisfy every hard constraint")
        if self.audit.quality_approved_count != self.question_count:
            raise ValueError("every optimized question must pass quality review")
        if self.audit.selected_duplicate_pair_count != 0:
            raise ValueError("optimized paper cannot contain duplicate pairs")
        return self

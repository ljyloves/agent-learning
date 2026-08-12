"""CP-SAT optimization for coverage, difficulty, diversity, and quality."""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CoreCompetencyModel,
    KnowledgePointModel,
    QuestionAnalysisModel,
    QuestionCoreCompetencyModel,
    QuestionKnowledgePointModel,
    QuestionModel,
    QuestionOptionModel,
)
from app.modules.paper_agent.schemas.analysis import (
    DifficultyEstimationLLMOutput,
    QualityReviewLLMOutput,
)
from app.modules.paper_agent.schemas.optimization import (
    ConstraintAudit,
    DifficultyQuota,
    OptimizedPaperRequest,
    OptimizedPaperResult,
    OptimizedQuestion,
    OptimizedSection,
)
from app.modules.paper_agent.schemas.question import QuestionType
from app.modules.paper_agent.schemas.retrieval import DuplicateQuestionMatch
from app.modules.paper_agent.services.deduplication import (
    DeduplicationCandidate,
    deduplicate_candidates,
)
from app.services.embedding import embed


EmbeddingFunction = Callable[[list[str]], Awaitable[list[list[float]]]]


class OptimizationFilterError(ValueError):
    pass


class OptimizationDataError(ValueError):
    pass


class OptimizationEmbeddingError(RuntimeError):
    pass


class RequiredQuestionUnavailableError(ValueError):
    def __init__(self, question_ids: Sequence[str]) -> None:
        self.question_ids = tuple(sorted(question_ids))
        super().__init__(
            "required questions are unavailable or fail current constraints: "
            + ", ".join(self.question_ids)
        )


class NoFeasiblePaperError(ValueError):
    def __init__(
        self,
        *,
        candidate_count: int,
        quota_availability: dict[str, int],
    ) -> None:
        self.candidate_count = candidate_count
        self.quota_availability = quota_availability
        super().__init__(
            "no paper satisfies all coverage, difficulty, diversity, and quality constraints"
        )


@dataclass(frozen=True, slots=True)
class OptimizationCandidate:
    question_id: str
    source_id: str
    question_type: QuestionType
    content: str
    knowledge_point_codes: tuple[str, ...]
    core_competency_codes: tuple[str, ...]
    difficulty_analysis_id: str
    difficulty_level: int
    estimated_correct_rate: float
    difficulty_confidence: float
    quality_analysis_id: str


def _quota_key(question_type: QuestionType, difficulty_level: int) -> str:
    return f"{question_type.value}:{difficulty_level}"


async def _validate_coverage_targets(
    session: AsyncSession,
    request: OptimizedPaperRequest,
) -> None:
    requested_codes = {target.code for target in request.coverage.targets}
    valid_codes = set(
        await session.scalars(
            select(KnowledgePointModel.code).where(
                KnowledgePointModel.code.in_(requested_codes),
                KnowledgePointModel.module_code == request.module_code,
                KnowledgePointModel.is_active.is_(True),
            )
        )
    )
    invalid_codes = sorted(requested_codes - valid_codes)
    if invalid_codes:
        raise OptimizationFilterError(
            "unknown, inactive, or out-of-module knowledge points: "
            + ", ".join(invalid_codes)
        )


def _latest_analyses(
    rows: Sequence[QuestionAnalysisModel],
) -> dict[tuple[str, str], QuestionAnalysisModel]:
    latest: dict[tuple[str, str], QuestionAnalysisModel] = {}
    for row in rows:
        latest.setdefault((row.question_id, row.analysis_type), row)
    return latest


def _validated_difficulty(row: QuestionAnalysisModel) -> DifficultyEstimationLLMOutput:
    try:
        return DifficultyEstimationLLMOutput.model_validate(row.result)
    except ValidationError as exc:
        raise OptimizationDataError(
            f"invalid difficulty analysis {row.analysis_id}"
        ) from exc


def _validated_quality_passed(row: QuestionAnalysisModel) -> bool:
    try:
        output = QualityReviewLLMOutput.model_validate(
            {
                "issues": row.result.get("issues"),
                "summary": row.result.get("summary"),
            }
        )
    except (AttributeError, ValidationError) as exc:
        raise OptimizationDataError(
            f"invalid quality analysis {row.analysis_id}"
        ) from exc
    passed = row.result.get("passed")
    if not isinstance(passed, bool) or passed != (not output.issues):
        raise OptimizationDataError(
            f"inconsistent quality analysis {row.analysis_id}"
        )
    return passed


async def _load_candidates(
    session: AsyncSession,
    request: OptimizedPaperRequest,
    *,
    allowed_question_ids: Sequence[str] | None = None,
    additional_excluded_question_ids: Sequence[str] = (),
) -> list[OptimizationCandidate]:
    await _validate_coverage_targets(session, request)
    excluded_ids = set(request.exclude_question_ids) | set(
        additional_excluded_question_ids
    )
    allowed_ids = (
        set(allowed_question_ids)
        if allowed_question_ids is not None
        else None
    )
    knowledge_rows = (
        await session.execute(
            select(
                QuestionKnowledgePointModel.question_id,
                KnowledgePointModel.code,
            )
            .join(
                KnowledgePointModel,
                KnowledgePointModel.code
                == QuestionKnowledgePointModel.knowledge_point_code,
            )
            .where(
                KnowledgePointModel.module_code == request.module_code,
                KnowledgePointModel.is_active.is_(True),
            )
            .order_by(
                QuestionKnowledgePointModel.question_id,
                KnowledgePointModel.code,
            )
        )
    ).all()
    knowledge_by_question: dict[str, list[str]] = {}
    for question_id, code in knowledge_rows:
        if (
            question_id not in excluded_ids
            and (allowed_ids is None or question_id in allowed_ids)
        ):
            knowledge_by_question.setdefault(question_id, []).append(code)
    question_ids = sorted(knowledge_by_question)
    if not question_ids:
        return []

    questions = {
        question.id: question
        for question in await session.scalars(
            select(QuestionModel).where(
                QuestionModel.id.in_(question_ids),
                QuestionModel.parent_question_id.is_(None),
            )
        )
    }
    competency_rows = (
        await session.execute(
            select(
                QuestionCoreCompetencyModel.question_id,
                CoreCompetencyModel.code,
            )
            .join(
                CoreCompetencyModel,
                CoreCompetencyModel.code
                == QuestionCoreCompetencyModel.competency_code,
            )
            .where(
                QuestionCoreCompetencyModel.question_id.in_(question_ids),
                CoreCompetencyModel.is_active.is_(True),
            )
            .order_by(
                QuestionCoreCompetencyModel.question_id,
                CoreCompetencyModel.code,
            )
        )
    ).all()
    competencies_by_question: dict[str, list[str]] = {}
    for question_id, code in competency_rows:
        competencies_by_question.setdefault(question_id, []).append(code)

    option_rows = (
        await session.execute(
            select(
                QuestionOptionModel.question_id,
                QuestionOptionModel.label,
                QuestionOptionModel.content,
            )
            .where(QuestionOptionModel.question_id.in_(question_ids))
            .order_by(
                QuestionOptionModel.question_id,
                QuestionOptionModel.position,
            )
        )
    ).all()
    options_by_question: dict[str, list[str]] = {}
    for question_id, label, content in option_rows:
        options_by_question.setdefault(question_id, []).append(
            f"{label}. {content or ''}".strip()
        )

    analysis_rows = list(
        await session.scalars(
            select(QuestionAnalysisModel)
            .where(QuestionAnalysisModel.question_id.in_(question_ids))
            .order_by(
                QuestionAnalysisModel.question_id,
                QuestionAnalysisModel.analysis_type,
                QuestionAnalysisModel.created_at.desc(),
                QuestionAnalysisModel.analysis_id.desc(),
            )
        )
    )
    analyses = _latest_analyses(analysis_rows)
    quota_keys = {
        (quota.question_type, quota.difficulty_level)
        for quota in request.difficulty_quotas
    }

    candidates: list[OptimizationCandidate] = []
    for question_id in question_ids:
        question = questions.get(question_id)
        competencies = competencies_by_question.get(question_id, [])
        difficulty_row = analyses.get((question_id, "difficulty_estimation"))
        quality_row = analyses.get((question_id, "quality_review"))
        if (
            question is None
            or not competencies
            or difficulty_row is None
            or quality_row is None
        ):
            continue
        difficulty = _validated_difficulty(difficulty_row)
        question_type = QuestionType(question.question_type)
        if (question_type, difficulty.difficulty_level) not in quota_keys:
            continue
        if not _validated_quality_passed(quality_row):
            continue
        content = "\n".join(
            [question.stem, *options_by_question.get(question_id, [])]
        )
        candidates.append(
            OptimizationCandidate(
                question_id=question_id,
                source_id=question.source_id,
                question_type=question_type,
                content=content,
                knowledge_point_codes=tuple(knowledge_by_question[question_id]),
                core_competency_codes=tuple(competencies),
                difficulty_analysis_id=difficulty_row.analysis_id,
                difficulty_level=difficulty.difficulty_level,
                estimated_correct_rate=difficulty.estimated_correct_rate,
                difficulty_confidence=difficulty.confidence,
                quality_analysis_id=quality_row.analysis_id,
            )
        )
    return candidates


async def _duplicate_matches(
    candidates: Sequence[OptimizationCandidate],
    threshold: float,
    embedder: EmbeddingFunction,
) -> tuple[DuplicateQuestionMatch, ...]:
    if not candidates:
        return ()
    try:
        vectors = await embedder([candidate.content for candidate in candidates])
    except Exception as exc:
        raise OptimizationEmbeddingError(
            "candidate embedding failed during optimization"
        ) from exc
    dimensions = {len(vector) for vector in vectors}
    if (
        len(vectors) != len(candidates)
        or dimensions == {0}
        or len(dimensions) != 1
    ):
        raise OptimizationEmbeddingError(
            "candidate embedding output is incomplete"
        )
    try:
        result = deduplicate_candidates(
            [
                DeduplicationCandidate(
                    question_id=candidate.question_id,
                    question_type=candidate.question_type.value,
                    content=candidate.content,
                )
                for candidate in candidates
            ],
            vectors,
            semantic_similarity_threshold=threshold,
        )
    except ValueError as exc:
        raise OptimizationEmbeddingError(
            "candidate embedding output is invalid"
        ) from exc
    return result.duplicates


def _link_presence(
    model: cp_model.CpModel,
    variables: Sequence[cp_model.IntVar],
    name: str,
) -> cp_model.IntVar:
    present = model.new_bool_var(name)
    if variables:
        model.add(sum(variables) >= present)
        model.add(sum(variables) <= len(variables) * present)
    else:
        model.add(present == 0)
    return present


def _quota_availability(
    request: OptimizedPaperRequest,
    candidates: Sequence[OptimizationCandidate],
) -> dict[str, int]:
    return {
        _quota_key(quota.question_type, quota.difficulty_level): sum(
            candidate.question_type == quota.question_type
            and candidate.difficulty_level == quota.difficulty_level
            for candidate in candidates
        )
        for quota in request.difficulty_quotas
    }


def _solve(
    request: OptimizedPaperRequest,
    candidates: Sequence[OptimizationCandidate],
    duplicates: Sequence[DuplicateQuestionMatch],
    required_question_ids: Sequence[str],
) -> set[str]:
    model = cp_model.CpModel()
    selected = {
        candidate.question_id: model.new_bool_var(
            f"selected_{index}"
        )
        for index, candidate in enumerate(candidates)
    }
    missing_required_ids = set(required_question_ids) - set(selected)
    if missing_required_ids:
        raise RequiredQuestionUnavailableError(missing_required_ids)
    for question_id in required_question_ids:
        model.add(selected[question_id] == 1)
    for quota in request.difficulty_quotas:
        eligible = [
            selected[candidate.question_id]
            for candidate in candidates
            if candidate.question_type == quota.question_type
            and candidate.difficulty_level == quota.difficulty_level
        ]
        model.add(sum(eligible) == quota.count)

    target_presence: dict[str, cp_model.IntVar] = {}
    target_by_code = {target.code: target for target in request.coverage.targets}
    for code, target in target_by_code.items():
        variables = [
            selected[candidate.question_id]
            for candidate in candidates
            if code in candidate.knowledge_point_codes
        ]
        target_presence[code] = _link_presence(
            model,
            variables,
            f"target_{code}",
        )
        if target.minimum_count:
            model.add(sum(variables) >= target.minimum_count)
    required_covered = math.ceil(
        request.coverage.minimum_coverage_rate * len(target_presence)
    )
    model.add(sum(target_presence.values()) >= required_covered)

    knowledge_codes = sorted(
        {
            code
            for candidate in candidates
            for code in candidate.knowledge_point_codes
        }
    )
    knowledge_presence: dict[str, cp_model.IntVar] = {}
    for code in knowledge_codes:
        variables = [
            selected[candidate.question_id]
            for candidate in candidates
            if code in candidate.knowledge_point_codes
        ]
        knowledge_presence[code] = _link_presence(
            model,
            variables,
            f"knowledge_{code}",
        )
        maximum = request.diversity.maximum_questions_per_knowledge_point
        if maximum is not None:
            model.add(sum(variables) <= maximum)
    model.add(
        sum(knowledge_presence.values())
        >= request.diversity.minimum_distinct_knowledge_points
    )

    competency_codes = sorted(
        {
            code
            for candidate in candidates
            for code in candidate.core_competency_codes
        }
    )
    competency_presence = {
        code: _link_presence(
            model,
            [
                selected[candidate.question_id]
                for candidate in candidates
                if code in candidate.core_competency_codes
            ],
            f"competency_{code}",
        )
        for code in competency_codes
    }
    model.add(
        sum(competency_presence.values())
        >= request.diversity.minimum_distinct_core_competencies
    )

    source_ids = sorted({candidate.source_id for candidate in candidates})
    source_presence: dict[str, cp_model.IntVar] = {}
    for index, source_id in enumerate(source_ids):
        variables = [
            selected[candidate.question_id]
            for candidate in candidates
            if candidate.source_id == source_id
        ]
        source_presence[source_id] = _link_presence(
            model,
            variables,
            f"source_{index}",
        )
        maximum = request.diversity.maximum_questions_per_source
        if maximum is not None:
            model.add(sum(variables) <= maximum)
    model.add(
        sum(source_presence.values())
        >= request.diversity.minimum_distinct_sources
    )

    for duplicate in duplicates:
        left = selected.get(duplicate.question_id)
        right = selected.get(duplicate.retained_question_id)
        if left is not None and right is not None:
            model.add(left + right <= 1)

    objective: list[Any] = []
    objective.extend(variable * 10000 for variable in knowledge_presence.values())
    objective.extend(variable * 2000 for variable in competency_presence.values())
    objective.extend(variable * 500 for variable in source_presence.values())
    for index, candidate in enumerate(candidates):
        confidence_score = round(candidate.difficulty_confidence * 100)
        tie_breaker = (request.random_seed + index * 17) % 11
        objective.append(
            selected[candidate.question_id] * (confidence_score + tie_breaker)
        )
    model.maximize(sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = request.random_seed
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise NoFeasiblePaperError(
            candidate_count=len(candidates),
            quota_availability=_quota_availability(request, candidates),
        )
    return {
        question_id
        for question_id, variable in selected.items()
        if solver.value(variable)
    }


def _audit(
    request: OptimizedPaperRequest,
    selected: Sequence[OptimizationCandidate],
    duplicates: Sequence[DuplicateQuestionMatch],
) -> ConstraintAudit:
    selected_ids = {candidate.question_id for candidate in selected}
    selected_knowledge = {
        code for candidate in selected for code in candidate.knowledge_point_codes
    }
    selected_competencies = {
        code for candidate in selected for code in candidate.core_competency_codes
    }
    selected_sources = {candidate.source_id for candidate in selected}
    target_codes = {target.code for target in request.coverage.targets}
    covered_targets = target_codes & selected_knowledge
    missing_targets = target_codes - covered_targets
    duplicate_count = sum(
        duplicate.question_id in selected_ids
        and duplicate.retained_question_id in selected_ids
        for duplicate in duplicates
    )
    coverage_rate = len(covered_targets) / len(target_codes)
    minimum_counts_satisfied = all(
        sum(target.code in candidate.knowledge_point_codes for candidate in selected)
        >= target.minimum_count
        for target in request.coverage.targets
    )
    maximum_knowledge = request.diversity.maximum_questions_per_knowledge_point
    maximum_source = request.diversity.maximum_questions_per_source
    satisfied = all(
        [
            len(selected) == request.question_count,
            coverage_rate >= request.coverage.minimum_coverage_rate,
            minimum_counts_satisfied,
            len(selected_knowledge)
            >= request.diversity.minimum_distinct_knowledge_points,
            len(selected_competencies)
            >= request.diversity.minimum_distinct_core_competencies,
            len(selected_sources) >= request.diversity.minimum_distinct_sources,
            maximum_knowledge is None
            or all(
                sum(code in candidate.knowledge_point_codes for candidate in selected)
                <= maximum_knowledge
                for code in selected_knowledge
            ),
            maximum_source is None
            or all(
                sum(candidate.source_id == source_id for candidate in selected)
                <= maximum_source
                for source_id in selected_sources
            ),
            duplicate_count == 0,
        ]
    )
    return ConstraintAudit(
        satisfied=satisfied,
        coverage_rate=coverage_rate,
        target_knowledge_point_codes=sorted(target_codes),
        covered_knowledge_point_codes=sorted(covered_targets),
        missing_knowledge_point_codes=sorted(missing_targets),
        distinct_knowledge_point_count=len(selected_knowledge),
        distinct_core_competency_count=len(selected_competencies),
        distinct_source_count=len(selected_sources),
        quality_approved_count=len(selected),
        selected_duplicate_pair_count=duplicate_count,
    )


async def optimize_paper(
    session: AsyncSession,
    request: OptimizedPaperRequest,
    *,
    embedder: EmbeddingFunction = embed,
    required_question_ids: Sequence[str] = (),
    allowed_question_ids: Sequence[str] | None = None,
    additional_excluded_question_ids: Sequence[str] = (),
) -> OptimizedPaperResult:
    if len(required_question_ids) != len(set(required_question_ids)):
        raise ValueError("required_question_ids must be unique")
    candidates = await _load_candidates(
        session,
        request,
        allowed_question_ids=allowed_question_ids,
        additional_excluded_question_ids=additional_excluded_question_ids,
    )
    duplicates = await _duplicate_matches(
        candidates,
        request.diversity.semantic_similarity_threshold,
        embedder,
    )
    selected_ids = _solve(
        request,
        candidates,
        duplicates,
        required_question_ids,
    )
    candidates_by_id = {
        candidate.question_id: candidate for candidate in candidates
    }
    selected_candidates = [
        candidates_by_id[question_id] for question_id in sorted(selected_ids)
    ]
    sections: list[OptimizedSection] = []
    for section_index, quota in enumerate(request.difficulty_quotas):
        questions = [
            candidate
            for candidate in selected_candidates
            if candidate.question_type == quota.question_type
            and candidate.difficulty_level == quota.difficulty_level
        ]
        sections.append(
            OptimizedSection(
                section_index=section_index,
                question_type=quota.question_type,
                difficulty_level=quota.difficulty_level,
                count=quota.count,
                score_per_question=quota.score_per_question,
                questions=[
                    OptimizedQuestion(
                        question_id=candidate.question_id,
                        question_type=candidate.question_type,
                        difficulty_level=candidate.difficulty_level,
                        estimated_correct_rate=candidate.estimated_correct_rate,
                        score=quota.score_per_question,
                        source_id=candidate.source_id,
                        knowledge_point_codes=list(
                            candidate.knowledge_point_codes
                        ),
                        core_competency_codes=list(
                            candidate.core_competency_codes
                        ),
                        difficulty_analysis_id=candidate.difficulty_analysis_id,
                        quality_analysis_id=candidate.quality_analysis_id,
                    )
                    for candidate in questions
                ],
            )
        )
    return OptimizedPaperResult(
        module_code=request.module_code,
        question_count=request.question_count,
        total_score=request.total_score,
        sections=sections,
        audit=_audit(request, selected_candidates, duplicates),
    )


async def candidate_question_ids_for_optimization(
    session: AsyncSession,
    request: OptimizedPaperRequest,
) -> list[str]:
    candidates = await _load_candidates(session, request)
    return [candidate.question_id for candidate in candidates]

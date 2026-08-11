"""Deterministic exact and embedding-assisted semantic deduplication."""

from __future__ import annotations

import hashlib
import math
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.modules.paper_agent.schemas.retrieval import (
    DeduplicationReport,
    DuplicateQuestionMatch,
)


@dataclass(frozen=True, slots=True)
class DeduplicationCandidate:
    question_id: str
    question_type: str
    content: str


@dataclass(frozen=True, slots=True)
class DeduplicationResult:
    retained_ids: tuple[str, ...]
    duplicates: tuple[DuplicateQuestionMatch, ...]
    report: DeduplicationReport


def normalize_question_content(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in normalized if character.isalnum())


def exact_fingerprint(candidate: DeduplicationCandidate) -> str:
    identity = f"{candidate.question_type}\n{normalize_question_content(candidate.content)}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("semantic vectors must have the same non-zero dimension")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def _lexical_guard(left: str, right: str) -> bool:
    normalized_left = normalize_question_content(left)
    normalized_right = normalize_question_content(right)
    if not normalized_left or not normalized_right:
        return False
    length_ratio = min(len(normalized_left), len(normalized_right)) / max(
        len(normalized_left), len(normalized_right)
    )
    surface_similarity = SequenceMatcher(
        None,
        normalized_left,
        normalized_right,
        autojunk=False,
    ).ratio()
    return length_ratio >= 0.65 and surface_similarity >= 0.35


def deduplicate_candidates(
    candidates: Sequence[DeduplicationCandidate],
    vectors: Sequence[Sequence[float]],
    *,
    semantic_similarity_threshold: float,
) -> DeduplicationResult:
    if len(candidates) != len(vectors):
        raise ValueError("one semantic vector is required for each candidate")

    retained_indexes: list[int] = []
    exact_owners: dict[str, int] = {}
    duplicates: list[DuplicateQuestionMatch] = []
    exact_count = 0
    semantic_count = 0

    for index, candidate in enumerate(candidates):
        fingerprint = exact_fingerprint(candidate)
        exact_owner = exact_owners.get(fingerprint)
        if exact_owner is not None:
            duplicates.append(
                DuplicateQuestionMatch(
                    question_id=candidate.question_id,
                    retained_question_id=candidates[exact_owner].question_id,
                    kind="exact",
                    similarity=1.0,
                )
            )
            exact_count += 1
            continue

        semantic_owner = None
        semantic_score = 0.0
        for retained_index in retained_indexes:
            retained = candidates[retained_index]
            if retained.question_type != candidate.question_type:
                continue
            if not _lexical_guard(retained.content, candidate.content):
                continue
            similarity = cosine_similarity(vectors[retained_index], vectors[index])
            if similarity >= semantic_similarity_threshold:
                semantic_owner = retained_index
                semantic_score = similarity
                break

        if semantic_owner is not None:
            duplicates.append(
                DuplicateQuestionMatch(
                    question_id=candidate.question_id,
                    retained_question_id=candidates[semantic_owner].question_id,
                    kind="semantic",
                    similarity=semantic_score,
                )
            )
            semantic_count += 1
            continue

        exact_owners[fingerprint] = index
        retained_indexes.append(index)

    retained_ids = tuple(candidates[index].question_id for index in retained_indexes)
    duplicate_matches = tuple(duplicates)
    return DeduplicationResult(
        retained_ids=retained_ids,
        duplicates=duplicate_matches,
        report=DeduplicationReport(
            input_count=len(candidates),
            exact_duplicate_count=exact_count,
            semantic_duplicate_count=semantic_count,
            retained_count=len(retained_ids),
            output_count=len(retained_ids),
            remaining_duplicate_ratio=0.0,
            matches=list(duplicate_matches),
        ),
    )

import unittest

from pydantic import ValidationError

from app.modules.paper_agent.schemas.assembly import (
    AssembledQuestion,
    AssembledSection,
    PaperAssemblyRequest,
    PaperAssemblyResult,
    PaperSectionConstraint,
)
from app.modules.paper_agent.schemas.question import (
    QuestionDifficulty,
    QuestionType,
)


def section(
    *,
    count: int = 2,
    score_per_question: int = 5,
) -> PaperSectionConstraint:
    return PaperSectionConstraint(
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty=QuestionDifficulty.MEDIUM,
        count=count,
        score_per_question=score_per_question,
    )


class PaperAssemblySchemaTests(unittest.TestCase):
    def test_request_requires_exact_question_count(self):
        with self.assertRaises(ValidationError):
            PaperAssemblyRequest(
                question_count=3,
                total_score=10,
                sections=[section()],
            )

    def test_request_requires_exact_total_score(self):
        with self.assertRaises(ValidationError):
            PaperAssemblyRequest(
                question_count=2,
                total_score=9,
                sections=[section()],
            )

    def test_request_rejects_duplicate_type_difficulty_sections(self):
        with self.assertRaises(ValidationError):
            PaperAssemblyRequest(
                question_count=4,
                total_score=20,
                sections=[section(), section()],
            )

    def test_result_rejects_question_that_does_not_match_section(self):
        with self.assertRaises(ValidationError):
            AssembledSection(
                section_index=0,
                question_type=QuestionType.SINGLE_CHOICE,
                difficulty=QuestionDifficulty.EASY,
                count=1,
                score_per_question=4,
                questions=[
                    AssembledQuestion(
                        question_id="question-1",
                        question_type=QuestionType.TRUE_FALSE,
                        difficulty=QuestionDifficulty.EASY,
                        score=4,
                    )
                ],
            )

    def test_result_rejects_incorrect_total_score(self):
        assembled_section = AssembledSection(
            section_index=0,
            question_type=QuestionType.SINGLE_CHOICE,
            difficulty=QuestionDifficulty.EASY,
            count=1,
            score_per_question=4,
            questions=[
                AssembledQuestion(
                    question_id="question-1",
                    question_type=QuestionType.SINGLE_CHOICE,
                    difficulty=QuestionDifficulty.EASY,
                    score=4,
                )
            ],
        )
        with self.assertRaises(ValidationError):
            PaperAssemblyResult(
                module_code="BIO-M1",
                question_count=1,
                total_score=5,
                sections=[assembled_section],
            )


if __name__ == "__main__":
    unittest.main()

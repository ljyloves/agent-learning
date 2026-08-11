import unittest

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import QuestionModel
from app.modules.paper_agent.schemas.assembly import (
    PaperAssemblyRequest,
    PaperSectionConstraint,
)
from app.modules.paper_agent.schemas.question import (
    QuestionDifficulty,
    QuestionType,
)
from app.modules.paper_agent.services.assembly import (
    InsufficientQuestionBankError,
    assemble_paper,
)


def strict_request(
    *,
    exclude_question_ids: list[str] | None = None,
    random_seed: int = 17,
) -> PaperAssemblyRequest:
    return PaperAssemblyRequest(
        module_code="BIO-M1",
        question_count=7,
        total_score=26,
        sections=[
            PaperSectionConstraint(
                question_type=QuestionType.SINGLE_CHOICE,
                difficulty=QuestionDifficulty.EASY,
                count=3,
                score_per_question=4,
            ),
            PaperSectionConstraint(
                question_type=QuestionType.TRUE_FALSE,
                difficulty=QuestionDifficulty.MEDIUM,
                count=2,
                score_per_question=2,
            ),
            PaperSectionConstraint(
                question_type=QuestionType.FILL_BLANK,
                difficulty=QuestionDifficulty.HARD,
                count=2,
                score_per_question=5,
            ),
        ],
        exclude_question_ids=exclude_question_ids or [],
        random_seed=random_seed,
    )


def selected_question_ids(result) -> list[str]:
    return [
        question.question_id
        for section in result.sections
        for question in section.questions
    ]


class BasicPaperAssemblyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            settings.database_url,
            poolclass=NullPool,
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_algorithm_strictly_matches_blueprint(self):
        request = strict_request()
        async with self.sessions() as session:
            result = await assemble_paper(session, request)
            selected_ids = selected_question_ids(result)
            rows = (
                await session.execute(
                    select(
                        QuestionModel.id,
                        QuestionModel.question_type,
                        QuestionModel.difficulty,
                    ).where(QuestionModel.id.in_(selected_ids))
                )
            ).all()

        self.assertEqual(result.question_count, 7)
        self.assertEqual(result.total_score, 26)
        self.assertEqual(len(selected_ids), 7)
        self.assertEqual(len(set(selected_ids)), 7)
        actual_constraints = {
            (question_type, difficulty)
            for _, question_type, difficulty in rows
        }
        self.assertEqual(
            actual_constraints,
            {
                ("single_choice", "easy"),
                ("true_false", "medium"),
                ("fill_blank", "hard"),
            },
        )

    async def test_same_seed_is_deterministic_and_exclusions_are_respected(self):
        async with self.sessions() as session:
            first = await assemble_paper(session, strict_request())
            repeated = await assemble_paper(session, strict_request())
            first_ids = selected_question_ids(first)
            repeated_ids = selected_question_ids(repeated)
            replacement = await assemble_paper(
                session,
                strict_request(exclude_question_ids=first_ids),
            )

        self.assertEqual(first_ids, repeated_ids)
        self.assertTrue(set(first_ids).isdisjoint(selected_question_ids(replacement)))

    async def test_inventory_shortage_fails_without_partial_result(self):
        request = PaperAssemblyRequest(
            module_code="BIO-M1",
            question_count=100,
            total_score=100,
            sections=[
                PaperSectionConstraint(
                    question_type=QuestionType.TRUE_FALSE,
                    difficulty=QuestionDifficulty.HARD,
                    count=100,
                    score_per_question=1,
                )
            ],
        )

        async with self.sessions() as session:
            with self.assertRaises(InsufficientQuestionBankError) as context:
                await assemble_paper(session, request)

        self.assertEqual(context.exception.required, 100)
        self.assertLess(context.exception.available, 100)


if __name__ == "__main__":
    unittest.main()

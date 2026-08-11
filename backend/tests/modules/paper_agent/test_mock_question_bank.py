import unittest

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import (
    KnowledgePointModel,
    QuestionCoreCompetencyModel,
    QuestionKnowledgePointModel,
    QuestionModel,
    QuestionOptionModel,
    QuestionSourceModel,
)


MOCK_SOURCE_ID = "bio016-molecular-cell-mock-bank"


class MolecularCellMockQuestionBankTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            settings.database_url,
            poolclass=NullPool,
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_bank_contains_exactly_100_traceable_questions(self):
        async with self.sessions() as session:
            question_count = await session.scalar(
                select(func.count())
                .select_from(QuestionModel)
                .where(QuestionModel.source_id == MOCK_SOURCE_ID)
            )
            source = await session.get(QuestionSourceModel, MOCK_SOURCE_ID)

        self.assertEqual(question_count, 100)
        self.assertIsNotNone(source)
        self.assertEqual(source.external_id, "BIO-016")
        self.assertEqual(source.source_type, "manual")

    async def test_all_questions_are_tagged_as_molecular_and_cell(self):
        async with self.sessions() as session:
            knowledge_link_count = await session.scalar(
                select(func.count())
                .select_from(QuestionKnowledgePointModel)
                .join(
                    QuestionModel,
                    QuestionModel.id == QuestionKnowledgePointModel.question_id,
                )
                .join(
                    KnowledgePointModel,
                    KnowledgePointModel.code
                    == QuestionKnowledgePointModel.knowledge_point_code,
                )
                .where(
                    QuestionModel.source_id == MOCK_SOURCE_ID,
                    KnowledgePointModel.module_code == "BIO-M1",
                )
            )
            competency_link_count = await session.scalar(
                select(func.count())
                .select_from(QuestionCoreCompetencyModel)
                .join(
                    QuestionModel,
                    QuestionModel.id == QuestionCoreCompetencyModel.question_id,
                )
                .where(QuestionModel.source_id == MOCK_SOURCE_ID)
            )

        self.assertEqual(knowledge_link_count, 100)
        self.assertEqual(competency_link_count, 100)

    async def test_bank_has_expected_question_type_distribution(self):
        async with self.sessions() as session:
            rows = await session.execute(
                select(QuestionModel.question_type, func.count())
                .where(QuestionModel.source_id == MOCK_SOURCE_ID)
                .group_by(QuestionModel.question_type)
            )

        self.assertEqual(
            dict(rows.all()),
            {
                "fill_blank": 25,
                "single_choice": 50,
                "true_false": 25,
            },
        )

    async def test_questions_have_unique_stems_answers_and_explanations(self):
        async with self.sessions() as session:
            rows = (
                await session.execute(
                    select(
                        QuestionModel.stem,
                        QuestionModel.answer,
                        QuestionModel.explanation,
                    ).where(QuestionModel.source_id == MOCK_SOURCE_ID)
                )
            ).all()

        self.assertEqual(len(rows), 100)
        self.assertEqual(len({stem for stem, _, _ in rows}), 100)
        self.assertTrue(
            all(answer is not None and explanation for _, answer, explanation in rows)
        )

    async def test_every_single_choice_question_has_four_options(self):
        async with self.sessions() as session:
            rows = await session.execute(
                select(QuestionModel.id, func.count(QuestionOptionModel.id))
                .join(
                    QuestionOptionModel,
                    QuestionOptionModel.question_id == QuestionModel.id,
                )
                .where(
                    QuestionModel.source_id == MOCK_SOURCE_ID,
                    QuestionModel.question_type == "single_choice",
                )
                .group_by(QuestionModel.id)
            )

        option_counts = rows.all()
        self.assertEqual(len(option_counts), 50)
        self.assertTrue(all(count == 4 for _, count in option_counts))

    async def test_all_seven_molecular_cell_knowledge_points_are_covered(self):
        async with self.sessions() as session:
            covered_codes = set(
                await session.scalars(
                    select(QuestionKnowledgePointModel.knowledge_point_code)
                    .join(
                        QuestionModel,
                        QuestionModel.id
                        == QuestionKnowledgePointModel.question_id,
                    )
                    .where(QuestionModel.source_id == MOCK_SOURCE_ID)
                    .distinct()
                )
            )

        self.assertEqual(
            covered_codes,
            {f"BIO-M1-K{number:02d}" for number in range(1, 8)},
        )


if __name__ == "__main__":
    unittest.main()

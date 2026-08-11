import unittest
from unittest.mock import AsyncMock, MagicMock

from app.models import QuestionModel
from app.modules.paper_agent.schemas.question import (
    Question,
    QuestionDifficulty,
    QuestionType,
)
from app.modules.paper_agent.services.persistence import (
    QuestionPersistenceContext,
)


class QuestionPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_question_persists_declared_difficulty(self):
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        session.flush = AsyncMock()
        question = Question(
            id="hard-question",
            question_type=QuestionType.SHORT_ANSWER,
            difficulty=QuestionDifficulty.HARD,
            stem="Explain the mechanism.",
            source={
                "source_id": "difficulty-source",
                "source_type": "manual",
                "name": "Difficulty persistence test",
                "external_id": "BIO-017",
            },
        )

        await QuestionPersistenceContext(session).save_question(question)

        saved_question = next(
            call.args[0]
            for call in session.add.call_args_list
            if isinstance(call.args[0], QuestionModel)
        )
        self.assertEqual(saved_question.difficulty, "hard")


if __name__ == "__main__":
    unittest.main()

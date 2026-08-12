import math
import unittest
import warnings

from pydantic import ValidationError
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.modules.paper_agent.schemas.retrieval import (
    HybridQuestionSearchRequest,
    QuestionIndexRequest,
)
from app.modules.paper_agent.services.retrieval import (
    QuestionIndexSelectionError,
    hybrid_search_questions,
    index_questions,
    keyword_relevance,
)


async def deterministic_embed(texts: list[str]) -> list[list[float]]:
    vectors = []
    for text in texts:
        values = [0.0] * settings.embedding_dim
        values[0] = float(text.count("细胞膜") + text.count("磷脂"))
        values[1] = float(text.count("线粒体") + text.count("有氧呼吸"))
        values[2] = float(text.count("酶") + text.count("活化能"))
        values[3] = float(text.count("遗传") + text.count("DNA"))
        values[4] = 0.1
        norm = math.sqrt(sum(value * value for value in values))
        vectors.append([value / norm for value in values])
    return vectors


class HybridRetrievalSchemaTests(unittest.TestCase):
    def test_request_rejects_duplicate_filters_and_zero_weights(self):
        with self.assertRaises(ValidationError):
            HybridQuestionSearchRequest(
                query="细胞膜",
                knowledge_point_codes=["BIO-M1-K02", "BIO-M1-K02"],
                question_types=["single_choice"],
            )
        with self.assertRaises(ValidationError):
            HybridQuestionSearchRequest(
                query="细胞膜",
                knowledge_point_codes=["BIO-M1-K02"],
                question_types=["single_choice"],
                keyword_weight=0,
                vector_weight=0,
            )

    def test_exact_chinese_phrase_scores_above_unrelated_text(self):
        related = keyword_relevance(
            "细胞膜 选择透过性",
            "细胞膜具有选择透过性，基本支架是磷脂双分子层。",
        )
        unrelated = keyword_relevance(
            "细胞膜 选择透过性",
            "酶通过降低活化能提高化学反应速率。",
        )
        self.assertGreater(related, unrelated)
        self.assertGreater(related, 0.5)


class HybridRetrievalIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.qdrant = QdrantClient(":memory:")

    async def asyncTearDown(self):
        self.qdrant.close()
        await self.engine.dispose()

    async def test_indexes_bank_and_hard_filters_hybrid_candidates(self):
        async with self.sessions() as session:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Payload indexes have no effect in the local Qdrant.*",
                )
                indexed = await index_questions(
                    session,
                    QuestionIndexRequest(),
                    client=self.qdrant,
                    embedder=deterministic_embed,
                )
            result = await hybrid_search_questions(
                session,
                HybridQuestionSearchRequest(
                    query="细胞膜的选择透过性和磷脂双分子层",
                    knowledge_point_codes=["BIO-M1-K02"],
                    question_types=["single_choice"],
                    top_k=5,
                ),
                client=self.qdrant,
                embedder=deterministic_embed,
                candidate_limit=100,
            )
            vector_only = await hybrid_search_questions(
                session,
                HybridQuestionSearchRequest(
                    query="细胞膜的选择透过性和磷脂双分子层",
                    knowledge_point_codes=["BIO-M1-K02"],
                    question_types=["single_choice"],
                    top_k=1,
                    keyword_weight=0,
                    vector_weight=1,
                ),
                client=self.qdrant,
                embedder=deterministic_embed,
                candidate_limit=settings.paper_agent_retrieval_pool_size,
            )

        self.assertGreaterEqual(indexed.indexed_count, 100)
        self.assertGreater(result.keyword_candidate_count, 0)
        self.assertGreater(result.vector_candidate_count, 0)
        self.assertGreater(len(result.candidates), 0)
        self.assertLess(result.deduplication.remaining_duplicate_ratio, 0.02)
        self.assertTrue(
            all(
                candidate.question_type.value == "single_choice"
                and "BIO-M1-K02" in candidate.knowledge_point_codes
                for candidate in result.candidates
            )
        )
        self.assertTrue(
            all(candidate.vector_score is not None for candidate in result.candidates)
        )
        self.assertIn("细胞膜", result.candidates[0].stem)
        self.assertEqual(len(vector_only.candidates), 1)
        self.assertIsNotNone(vector_only.candidates[0].vector_score)
        self.assertIn(
            "BIO-M1-K02",
            vector_only.candidates[0].knowledge_point_codes,
        )

    async def test_rejects_unknown_or_untagged_index_selection(self):
        async with self.sessions() as session:
            with self.assertRaises(QuestionIndexSelectionError):
                await index_questions(
                    session,
                    QuestionIndexRequest(question_ids=["missing-question"]),
                    client=self.qdrant,
                    embedder=deterministic_embed,
                )


if __name__ == "__main__":
    unittest.main()

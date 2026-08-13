import hashlib
import unittest
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import QuestionModel, QuestionResourceModel, QuestionSourceModel
from app.modules.paper_agent.schemas.parsing import QuestionParseRequest
from app.modules.paper_agent.schemas.question import QuestionType
from app.modules.paper_agent.schemas.source import SourceType
from app.modules.paper_agent.services.document_extraction import DocumentExtractionError
from app.modules.paper_agent.services.source_library import (
    list_library_questions,
    list_sources,
    parse_questions_with_status,
)


class SourceLibraryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.temporary = TemporaryDirectory()
        self.source_id = f"bio043-{uuid.uuid4()}"
        self.resource_id = f"bio043-resource-{uuid.uuid4()}"
        self.question_id = str(uuid.uuid4())

    async def asyncTearDown(self):
        async with self.sessions() as session:
            await session.execute(
                delete(QuestionModel).where(QuestionModel.source_id == self.source_id)
            )
            await session.execute(
                delete(QuestionResourceModel).where(
                    QuestionResourceModel.source_id == self.source_id
                )
            )
            await session.execute(
                delete(QuestionSourceModel).where(
                    QuestionSourceModel.source_id == self.source_id
                )
            )
            await session.commit()
        self.temporary.cleanup()
        await self.engine.dispose()

    async def _seed(self):
        data = b"\x89PNG\r\n\x1a\nBIO-043"
        path = Path(self.temporary.name) / "biology.png"
        path.write_bytes(data)
        async with self.sessions() as session:
            session.add(
                QuestionSourceModel(
                    source_id=self.source_id,
                    source_type="file",
                    name="BIO-043 biology.png",
                    uri=str(path),
                    external_id="biology.png",
                    processing_status="uploaded",
                )
            )
            await session.flush()
            session.add(
                QuestionResourceModel(
                    resource_id=self.resource_id,
                    resource_type="image",
                    uri=str(path),
                    source_id=self.source_id,
                    mime_type="image/png",
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            )
            await session.flush()
            session.add(
                QuestionModel(
                    id=self.question_id,
                    source_id=self.source_id,
                    question_type="single_choice",
                    difficulty="medium",
                    stem="BIO-043 细胞膜的结构特点是什么？",
                    answer="A",
                )
            )
            await session.flush()
            session.add(
                QuestionModel(
                    id=str(uuid.uuid4()),
                    parent_question_id=self.question_id,
                    source_id=self.source_id,
                    question_type="short_answer",
                    difficulty="medium",
                    stem="说明原因。",
                    answer="略",
                )
            )
            await session.commit()

    async def test_lists_sources_with_root_question_count_and_provenance(self):
        await self._seed()
        async with self.sessions() as session:
            result = await list_sources(
                session,
                page=1,
                page_size=10,
                keyword="BIO-043",
                source_type=SourceType.FILE,
            )

        self.assertEqual(result.total, 1)
        item = result.items[0]
        self.assertEqual(item.question_count, 1)
        self.assertEqual(item.resource_id, self.resource_id)
        self.assertEqual(item.locator, "biology.png")
        self.assertFalse(item.can_parse)

    async def test_searches_root_questions_and_returns_source(self):
        await self._seed()
        async with self.sessions() as session:
            result = await list_library_questions(
                session,
                page=1,
                page_size=10,
                keyword="细胞膜",
                question_type=QuestionType.SINGLE_CHOICE,
                source_id=self.source_id,
            )

        self.assertEqual(result.total, 1)
        item = result.items[0]
        self.assertEqual(item.question_id, self.question_id)
        self.assertEqual(item.source_name, "BIO-043 biology.png")
        self.assertTrue(item.has_answer)

    async def test_persists_parse_failure_reason(self):
        await self._seed()
        async with self.sessions() as session:
            with self.assertRaises(DocumentExtractionError):
                await parse_questions_with_status(
                    session,
                    self.resource_id,
                    QuestionParseRequest(),
                    storage_root=Path(self.temporary.name),
                    max_asset_bytes=1024,
                )
            source = await session.get(QuestionSourceModel, self.source_id)

        self.assertEqual(source.processing_status, "failed")
        self.assertIn("documents", source.parse_failure_reason)
        self.assertIsNotNone(source.processed_at)


if __name__ == "__main__":
    unittest.main()

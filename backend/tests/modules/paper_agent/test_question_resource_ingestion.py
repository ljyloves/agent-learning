import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.datastructures import Headers

from app.config import settings
from app.models import (
    QuestionImageModel,
    QuestionKnowledgePointModel,
    QuestionModel,
    QuestionResourceModel,
    QuestionSourceModel,
)
from app.modules.paper_agent.schemas.parsing import QuestionParseRequest
from app.modules.paper_agent.services.file_ingestion import save_teacher_upload
from app.modules.paper_agent.services.question_ingestion import parse_uploaded_questions
from app.modules.paper_agent.services.resource_storage import (
    StoredResourceIntegrityError,
    get_stored_resource_file,
    recover_question,
)


PNG_DATA = b"\x89PNG\r\n\x1a\nquestion-diagram"


def make_question_docx() -> bytes:
    paragraphs = [
        "<w:p><w:r><w:t>1. 观察图示，下列结构正确的是</w:t></w:r>"
        "<w:r><w:drawing><a:blip r:embed=\"rId1\"/></w:drawing></w:r></w:p>",
        "<w:p><w:r><w:t>A. 细胞膜</w:t></w:r></w:p>",
        "<w:p><w:r><w:t>B. 细胞壁</w:t></w:r></w:p>",
        "<w:p><w:r><w:t>答案：A</w:t></w:r></w:p>",
        "<w:p><w:r><w:t>解析：图中标注的是细胞膜。</w:t></w:r></w:p>",
        "<w:p><w:r><w:t>2. 根据同一图示回答</w:t></w:r>"
        "<w:r><w:drawing><a:blip r:embed=\"rId1\"/></w:drawing></w:r></w:p>",
        "<w:p><w:r><w:t>(1) 遗传信息主要储存在哪里？</w:t></w:r></w:p>",
        "<w:p><w:r><w:t>(2) 控制物质进出的结构是什么？</w:t></w:r></w:p>",
        "<w:p><w:r><w:t>答案：(1) 细胞核 (2) 细胞膜</w:t></w:r></w:p>",
        "<w:p><w:r><w:t>解析：(1) 细胞核含遗传物质 (2) 细胞膜控制物质进出</w:t></w:r></w:p>",
    ]
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        f"<w:body>{''.join(paragraphs)}</w:body></w:document>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        'Target="media/diagram.png"/></Relationships>'
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", relationships)
        archive.writestr("word/media/diagram.png", PNG_DATA)
    return buffer.getvalue()


def docx_upload(content: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename="biology-questions.docx",
        headers=Headers(
            {
                "content-type": (
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                )
            }
        ),
    )


class QuestionResourceIngestionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.temporary = TemporaryDirectory()
        self.source_id = None

    async def asyncTearDown(self):
        if self.source_id is not None:
            async with self.sessions() as session:
                root_ids = list(
                    await session.scalars(
                        select(QuestionModel.id).where(
                            QuestionModel.source_id == self.source_id,
                            QuestionModel.parent_question_id.is_(None),
                        )
                    )
                )
                for question_id in root_ids:
                    question = await session.get(QuestionModel, question_id)
                    if question is not None:
                        await session.delete(question)
                await session.flush()
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

    async def test_docx_images_are_archived_shared_and_recoverable(self):
        root = Path(self.temporary.name)
        async with self.sessions() as session:
            uploaded = await save_teacher_upload(
                session,
                docx_upload(make_question_docx()),
                storage_root=root,
                max_bytes=1024 * 1024,
            )
            self.source_id = uploaded.source_id
            result = await parse_uploaded_questions(
                session,
                uploaded.resource_id,
                QuestionParseRequest(
                    knowledge_point_codes=["BIO-M1-K02"],
                ),
                storage_root=root,
                max_asset_bytes=1024 * 1024,
            )

            self.assertEqual(len(result.questions), 2)
            self.assertEqual(result.questions[0].answer, "A")
            self.assertEqual(result.questions[0].options[0].content, "细胞膜")
            self.assertEqual(len(result.questions[1].subquestions), 2)
            self.assertEqual(result.questions[1].subquestions[0].answer, "细胞核")
            self.assertEqual(len(result.asset_resource_ids), 1)
            tagged_count = await session.scalar(
                select(func.count())
                .select_from(QuestionKnowledgePointModel)
                .where(
                    QuestionKnowledgePointModel.question_id.in_(
                        result.question_ids
                    ),
                    QuestionKnowledgePointModel.knowledge_point_code
                    == "BIO-M1-K02",
                )
            )
            self.assertEqual(tagged_count, 2)

            image_id = result.asset_resource_ids[0]
            reference_count = await session.scalar(
                select(func.count())
                .select_from(QuestionImageModel)
                .where(QuestionImageModel.resource_id == image_id)
            )
            self.assertEqual(reference_count, 2)

            recovered = await recover_question(session, result.question_ids[0])
            self.assertEqual(recovered.images[0].resource_id, image_id)
            stored = await get_stored_resource_file(
                session,
                image_id,
                storage_root=root,
            )
            self.assertEqual(stored.path.read_bytes(), PNG_DATA)

            stored.path.write_bytes(b"tampered")
            with self.assertRaises(StoredResourceIntegrityError):
                await get_stored_resource_file(
                    session,
                    image_id,
                    storage_root=root,
                )


if __name__ == "__main__":
    unittest.main()

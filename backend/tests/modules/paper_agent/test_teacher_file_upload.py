import hashlib
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.datastructures import Headers

from app.config import settings
from app.models import QuestionResourceModel, QuestionSourceModel
from app.modules.paper_agent.services.file_ingestion import (
    UnsupportedUploadError,
    UploadTooLargeError,
    save_teacher_upload,
)


def make_docx() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return buffer.getvalue()


def upload(filename: str, mime_type: str, content: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": mime_type}),
    )


class TeacherFileUploadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.temporary = TemporaryDirectory()
        self.responses = []

    async def asyncTearDown(self):
        async with self.sessions() as session:
            for response in self.responses:
                resource = await session.get(
                    QuestionResourceModel,
                    response.resource_id,
                )
                if resource is not None:
                    await session.delete(resource)
                source = await session.get(QuestionSourceModel, response.source_id)
                if source is not None:
                    await session.delete(source)
                Path(response.storage_uri).unlink(missing_ok=True)
            await session.commit()
        self.temporary.cleanup()
        await self.engine.dispose()

    async def save(self, filename: str, mime_type: str, content: bytes):
        async with self.sessions() as session:
            result = await save_teacher_upload(
                session,
                upload(filename, mime_type, content),
                storage_root=Path(self.temporary.name),
                max_bytes=1024 * 1024,
            )
            self.responses.append(result)
            source = await session.get(QuestionSourceModel, result.source_id)
            resource = await session.get(
                QuestionResourceModel,
                result.resource_id,
            )
        self.assertIsNotNone(source)
        self.assertIsNotNone(resource)
        self.assertEqual(resource.source_id, source.source_id)
        self.assertEqual(resource.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(Path(result.storage_uri).read_bytes(), content)
        return result

    async def test_supports_pdf_word_and_image_uploads(self):
        samples = [
            ("paper.pdf", "application/pdf", b"%PDF-1.7\nmock"),
            (
                "paper.docx",
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document",
                make_docx(),
            ),
            (
                "paper.doc",
                "application/msword",
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1mock",
            ),
            ("diagram.png", "image/png", b"\x89PNG\r\n\x1a\nmock"),
        ]
        for filename, mime_type, content in samples:
            with self.subTest(filename=filename):
                result = await self.save(filename, mime_type, content)
                self.assertEqual(result.original_name, filename)

    async def test_rejects_mismatched_signature_and_path_filename(self):
        async with self.sessions() as session:
            with self.assertRaises(UnsupportedUploadError):
                await save_teacher_upload(
                    session,
                    upload("fake.pdf", "application/pdf", b"not-a-pdf"),
                    storage_root=Path(self.temporary.name),
                    max_bytes=1024,
                )
            with self.assertRaises(UnsupportedUploadError):
                await save_teacher_upload(
                    session,
                    upload("../paper.pdf", "application/pdf", b"%PDF-1.7"),
                    storage_root=Path(self.temporary.name),
                    max_bytes=1024,
                )

    async def test_rejects_file_over_size_limit(self):
        async with self.sessions() as session:
            with self.assertRaises(UploadTooLargeError):
                await save_teacher_upload(
                    session,
                    upload("large.pdf", "application/pdf", b"%PDF-" + b"x" * 20),
                    storage_root=Path(self.temporary.name),
                    max_bytes=10,
                )


if __name__ == "__main__":
    unittest.main()

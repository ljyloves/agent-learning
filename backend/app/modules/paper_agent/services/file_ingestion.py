"""Validated teacher-file storage with source provenance."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QuestionResourceModel, QuestionSourceModel
from app.modules.paper_agent.schemas.ingestion import IngestedResourceResponse
from app.modules.paper_agent.schemas.source import ResourceType, SourceType


class EmptyUploadError(ValueError):
    pass


class UploadTooLargeError(ValueError):
    pass


class UnsupportedUploadError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SupportedUpload:
    suffix: str
    mime_type: str
    resource_type: ResourceType
    declared_mime_types: frozenset[str]


GENERIC_MIME_TYPES = frozenset({"", "application/octet-stream"})
SUPPORTED_UPLOADS = {
    ".pdf": SupportedUpload(
        suffix=".pdf",
        mime_type="application/pdf",
        resource_type=ResourceType.DOCUMENT,
        declared_mime_types=frozenset({"application/pdf"}),
    ),
    ".docx": SupportedUpload(
        suffix=".docx",
        mime_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        resource_type=ResourceType.DOCUMENT,
        declared_mime_types=frozenset(
            {
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document",
                "application/zip",
            }
        ),
    ),
    ".doc": SupportedUpload(
        suffix=".doc",
        mime_type="application/msword",
        resource_type=ResourceType.DOCUMENT,
        declared_mime_types=frozenset({"application/msword"}),
    ),
    ".png": SupportedUpload(
        suffix=".png",
        mime_type="image/png",
        resource_type=ResourceType.IMAGE,
        declared_mime_types=frozenset({"image/png"}),
    ),
    ".jpg": SupportedUpload(
        suffix=".jpg",
        mime_type="image/jpeg",
        resource_type=ResourceType.IMAGE,
        declared_mime_types=frozenset({"image/jpeg", "image/jpg"}),
    ),
    ".jpeg": SupportedUpload(
        suffix=".jpeg",
        mime_type="image/jpeg",
        resource_type=ResourceType.IMAGE,
        declared_mime_types=frozenset({"image/jpeg", "image/jpg"}),
    ),
    ".gif": SupportedUpload(
        suffix=".gif",
        mime_type="image/gif",
        resource_type=ResourceType.IMAGE,
        declared_mime_types=frozenset({"image/gif"}),
    ),
    ".webp": SupportedUpload(
        suffix=".webp",
        mime_type="image/webp",
        resource_type=ResourceType.IMAGE,
        declared_mime_types=frozenset({"image/webp"}),
    ),
}


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, OSError):
        return False
    return "[Content_Types].xml" in names and any(
        name.startswith("word/") for name in names
    )


def _has_valid_signature(suffix: str, data: bytes) -> bool:
    signatures = {
        ".pdf": data.startswith(b"%PDF-"),
        ".doc": data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
        ".png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": data.startswith(b"\xff\xd8\xff"),
        ".jpeg": data.startswith(b"\xff\xd8\xff"),
        ".gif": data.startswith((b"GIF87a", b"GIF89a")),
        ".webp": (
            len(data) >= 12
            and data.startswith(b"RIFF")
            and data[8:12] == b"WEBP"
        ),
    }
    return _is_docx(data) if suffix == ".docx" else signatures.get(suffix, False)


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(64 * 1024):
        size += len(chunk)
        if size > max_bytes:
            raise UploadTooLargeError(f"file exceeds {max_bytes} bytes")
        chunks.append(chunk)
    if size == 0:
        raise EmptyUploadError("uploaded file is empty")
    return b"".join(chunks)


def _validate_upload(
    filename: str | None,
    content_type: str | None,
    data: bytes,
) -> tuple[str, SupportedUpload]:
    if filename is None or not filename.strip():
        raise EmptyUploadError("filename is required")
    if "/" in filename or "\\" in filename:
        raise UnsupportedUploadError("filename cannot contain a path")
    safe_name = Path(filename).name.strip()
    if safe_name != filename.strip() or len(safe_name) > 255:
        raise UnsupportedUploadError("filename is invalid")
    suffix = Path(safe_name).suffix.lower()
    supported = SUPPORTED_UPLOADS.get(suffix)
    if supported is None:
        raise UnsupportedUploadError("only PDF, Word, and image files are supported")
    declared_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if (
        declared_type not in GENERIC_MIME_TYPES
        and declared_type not in supported.declared_mime_types
    ):
        raise UnsupportedUploadError("declared MIME type does not match filename")
    if not _has_valid_signature(suffix, data):
        raise UnsupportedUploadError("file signature does not match its format")
    return safe_name, supported


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def save_teacher_upload(
    session: AsyncSession,
    upload: UploadFile,
    *,
    storage_root: Path,
    max_bytes: int,
) -> IngestedResourceResponse:
    data = await _read_limited(upload, max_bytes)
    original_name, supported = _validate_upload(
        upload.filename,
        upload.content_type,
        data,
    )
    source_id = str(uuid.uuid4())
    resource_id = str(uuid.uuid4())
    destination = storage_root / "uploads" / f"{resource_id}{supported.suffix}"
    await asyncio.to_thread(_write_atomic, destination, data)
    digest = hashlib.sha256(data).hexdigest()

    try:
        session.add(
            QuestionSourceModel(
                source_id=source_id,
                source_type=SourceType.FILE.value,
                name=original_name,
                uri=str(destination),
                external_id=original_name,
                processing_status="uploaded",
            )
        )
        await session.flush()
        session.add(
            QuestionResourceModel(
                resource_id=resource_id,
                resource_type=supported.resource_type.value,
                uri=str(destination),
                source_id=source_id,
                mime_type=supported.mime_type,
                sha256=digest,
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        await asyncio.to_thread(destination.unlink, missing_ok=True)
        raise

    return IngestedResourceResponse(
        source_id=source_id,
        resource_id=resource_id,
        source_type=SourceType.FILE,
        resource_type=supported.resource_type,
        original_name=original_name,
        storage_uri=str(destination),
        mime_type=supported.mime_type,
        sha256=digest,
        size_bytes=len(data),
    )

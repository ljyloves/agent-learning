"""Validated server-side DOCX to PDF conversion."""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

from docx import Document
from docx.oxml.ns import qn
from pypdf import PdfReader

from app.modules.paper_agent.services.render_validation import (
    DocumentRenderValidationError,
    RenderInspectionReport,
    inspect_rendered_document,
)
from app.modules.paper_agent.services.student_paper import StudentPaperWordFile


PDF_MIME_TYPE = "application/pdf"
CONVERSION_TIMEOUT_SECONDS = 60


class DocumentConverterUnavailableError(RuntimeError):
    pass


class DocumentConversionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PaperPdfFile:
    content: bytes
    filename: str
    page_count: int
    inspection: RenderInspectionReport


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _comparison_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character)[0] in {"L", "N"}
    ).casefold()


def _docx_text_blocks(content: bytes) -> tuple[str, ...]:
    try:
        document = Document(BytesIO(content))
    except Exception as exc:
        raise DocumentConversionError("generated DOCX cannot be opened") from exc
    blocks: list[str] = []
    for paragraph in document._element.body.iter(qn("w:p")):
        text = "".join(node.text or "" for node in paragraph.iter(qn("w:t")))
        normalized = _normalized_text(text)
        if len(normalized) >= 2 and normalized not in blocks:
            blocks.append(normalized)
    if not blocks:
        raise DocumentConversionError("generated DOCX contains no printable text")
    return tuple(blocks)


def _pdf_text_and_pages(content: bytes) -> tuple[str, int]:
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
        raise DocumentConversionError("converter returned an invalid PDF file")
    try:
        reader = PdfReader(BytesIO(content))
        page_count = len(reader.pages)
        text = "".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise DocumentConversionError("generated PDF cannot be opened") from exc
    if page_count < 1:
        raise DocumentConversionError("generated PDF contains no pages")
    return _normalized_text(text), page_count


def _assert_content_consistency(docx_content: bytes, pdf_content: bytes) -> int:
    blocks = _docx_text_blocks(docx_content)
    pdf_text, page_count = _pdf_text_and_pages(pdf_content)
    comparison_pdf = _comparison_text(pdf_text)
    missing = [
        block
        for block in blocks
        if _comparison_text(block) not in comparison_pdf
    ]
    if missing:
        preview = missing[0][:80]
        raise DocumentConversionError(
            f"PDF content does not match DOCX near: {preview}"
        )
    return page_count


def _find_converter() -> str:
    converter = shutil.which("soffice") or shutil.which("libreoffice")
    bundled = Path("/usr/lib/libreoffice/program/soffice")
    if converter is None and bundled.is_file():
        converter = str(bundled)
    if converter is None:
        raise DocumentConverterUnavailableError(
            "LibreOffice Writer is required for PDF export"
        )
    return converter


def _convert_docx_to_pdf(content: bytes) -> tuple[bytes, int]:
    converter = _find_converter()
    with TemporaryDirectory(prefix="flowgate-pdf-") as temporary:
        root = Path(temporary)
        source = root / "paper.docx"
        output = root / "paper.pdf"
        profile = root / "libreoffice-profile"
        source.write_bytes(content)
        command = [
            converter,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--nofirststartwizard",
            f"-env:UserInstallation=file://{quote(profile.resolve().as_posix())}",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(root),
            str(source),
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=CONVERSION_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise DocumentConversionError("DOCX to PDF conversion timed out") from exc
        except OSError as exc:
            raise DocumentConverterUnavailableError(
                "LibreOffice Writer could not be started"
            ) from exc
        if result.returncode != 0 or not output.is_file():
            detail = (result.stderr or result.stdout).strip()[-500:]
            raise DocumentConversionError(
                f"DOCX to PDF conversion failed: {detail or 'no output file'}"
            )
        pdf_content = output.read_bytes()
    return pdf_content, _assert_content_consistency(content, pdf_content)


def _convert_and_inspect(
    exported: StudentPaperWordFile,
) -> tuple[bytes, RenderInspectionReport]:
    content, page_count = _convert_docx_to_pdf(exported.content)
    try:
        inspection = inspect_rendered_document(
            exported.content,
            content,
            allow_answers=exported.allow_answers,
            protected_texts=exported.protected_texts,
        )
    except DocumentRenderValidationError as exc:
        raise DocumentConversionError(f"PDF render check failed: {exc}") from exc
    if inspection.page_count != page_count:
        raise DocumentConversionError("PDF page count changed during render check")
    return content, inspection


async def convert_word_export_to_pdf(
    exported: StudentPaperWordFile,
) -> PaperPdfFile:
    content, inspection = await asyncio.to_thread(
        _convert_and_inspect,
        exported,
    )
    filename = f"{Path(exported.filename).stem}.pdf"
    return PaperPdfFile(
        content=content,
        filename=filename,
        page_count=inspection.page_count,
        inspection=inspection,
    )

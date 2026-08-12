"""Text and embedded-image extraction for uploaded teacher documents."""

from __future__ import annotations

import mimetypes
import hashlib
import posixpath
import subprocess
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from pypdf import PdfReader


class DocumentExtractionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExtractedAsset:
    marker: str
    original_name: str
    suffix: str
    mime_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    text: str
    assets: list[ExtractedAsset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _PdfAssetCandidate:
    key: str
    digest: str
    asset: ExtractedAsset


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}


def _safe_word_target(target: str) -> str:
    normalized = posixpath.normpath(posixpath.join("word", target))
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not normalized.startswith("word/"):
        raise DocumentExtractionError("DOCX contains an unsafe media path")
    return normalized


def _docx_relationships(archive: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = ElementTree.fromstring(
            archive.read("word/_rels/document.xml.rels")
        )
    except KeyError:
        return {}
    except ElementTree.ParseError as exc:
        raise DocumentExtractionError("DOCX relationship XML is invalid") from exc
    return {
        node.attrib["Id"]: node.attrib["Target"]
        for node in root.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
        if "Id" in node.attrib and "Target" in node.attrib
    }


def _extract_docx(data: bytes) -> ExtractedDocument:
    try:
        archive = zipfile.ZipFile(BytesIO(data))
        document = ElementTree.fromstring(archive.read("word/document.xml"))
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise DocumentExtractionError("DOCX document XML is invalid") from exc

    relationships = _docx_relationships(archive)
    assets: dict[str, ExtractedAsset] = {}
    paragraphs: list[str] = []
    for paragraph in document.iter(f"{{{WORD_NS}}}p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{{{WORD_NS}}}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{{{WORD_NS}}}tab":
                parts.append("\t")
            elif node.tag == f"{{{WORD_NS}}}br":
                parts.append("\n")
            elif node.tag == f"{{{DRAWING_NS}}}blip":
                relation_id = node.attrib.get(f"{{{REL_NS}}}embed")
                target = relationships.get(relation_id or "")
                if target is None:
                    continue
                archive_name = _safe_word_target(target)
                suffix = PurePosixPath(archive_name).suffix.lower()
                if suffix not in IMAGE_SUFFIXES:
                    continue
                marker = f"docx-{relation_id}"
                if marker not in assets:
                    try:
                        image_data = archive.read(archive_name)
                    except KeyError as exc:
                        raise DocumentExtractionError(
                            "DOCX references a missing embedded image"
                        ) from exc
                    mime_type = mimetypes.guess_type(archive_name)[0] or "application/octet-stream"
                    assets[marker] = ExtractedAsset(
                        marker=marker,
                        original_name=PurePosixPath(archive_name).name,
                        suffix=suffix,
                        mime_type=mime_type,
                        data=image_data,
                    )
                parts.append(f"[[image:{marker}]]")
        content = "".join(parts).strip()
        if content:
            paragraphs.append(content)
    archive.close()
    return ExtractedDocument(text="\n".join(paragraphs), assets=list(assets.values()))


def _extract_pdf(data: bytes) -> ExtractedDocument:
    try:
        reader = PdfReader(BytesIO(data), strict=False)
    except Exception as exc:
        raise DocumentExtractionError("PDF cannot be read") from exc
    pages = list(reader.pages)
    paragraphs: list[str] = []
    assets: list[ExtractedAsset] = []
    warnings: list[str] = []
    candidates_by_page: list[dict[str, _PdfAssetCandidate]] = []
    digest_pages: dict[str, set[int]] = defaultdict(set)

    for page_number, page in enumerate(pages, start=1):
        page_candidates: dict[str, _PdfAssetCandidate] = {}
        try:
            page_images = list(page.images)
        except Exception:
            page_images = []
            warnings.append(f"page {page_number}: embedded images could not be decoded")
        for index, image in enumerate(page_images):
            image_data = image.data
            digest = hashlib.sha256(image_data).hexdigest()
            original_name = image.name or f"page-{page_number}-image-{index}.png"
            key = Path(original_name).stem.lstrip("/")
            suffix = Path(original_name).suffix.lower()
            if suffix not in IMAGE_SUFFIXES:
                suffix = ".png"
                original_name = f"{original_name}.png"
            candidate = _PdfAssetCandidate(
                key=key,
                digest=digest,
                asset=ExtractedAsset(
                    marker=f"pdf-{page_number}-{index}",
                    original_name=original_name,
                    suffix=suffix,
                    mime_type=(
                        mimetypes.guess_type(original_name)[0] or "image/png"
                    ),
                    data=image_data,
                ),
            )
            page_candidates.setdefault(key, candidate)
            digest_pages[digest].add(page_number)
        candidates_by_page.append(page_candidates)

    marker_by_digest: dict[str, str] = {}
    ignored_boilerplate = False
    boilerplate_text = {
        "学科网（北京）股份有限公司",
        "学科网(北京)股份有限公司",
    }
    for page_number, (page, page_candidates) in enumerate(
        zip(pages, candidates_by_page, strict=True),
        start=1,
    ):
        try:
            contents = page.get_contents()
            if contents is not None and len(contents.get_data()) > 50 * 1024 * 1024:
                raise DocumentExtractionError("PDF page content stream is too large")
            stream_parts: list[str] = []
            page_top = float(page.mediabox.top)

            def visitor_operand_before(operator, operands, cm, tm):
                nonlocal ignored_boilerplate
                if operator != b"Do" or not operands:
                    return
                key = str(operands[0]).lstrip("/")
                candidate = page_candidates.get(key)
                if candidate is None:
                    return
                y_position = float(cm[5])
                is_repeated_edge_image = (
                    len(digest_pages[candidate.digest]) >= 3
                    and (
                        y_position >= page_top * 0.9
                        or y_position <= page_top * 0.05
                    )
                )
                if is_repeated_edge_image:
                    ignored_boilerplate = True
                    return
                marker = marker_by_digest.get(candidate.digest)
                if marker is None:
                    marker = candidate.asset.marker
                    marker_by_digest[candidate.digest] = marker
                    assets.append(candidate.asset)
                stream_parts.append(f"\n[[image:{marker}]]\n")

            def visitor_text(text, cm, tm, font_dict, font_size):
                compact = "".join(text.split())
                if compact in boilerplate_text:
                    return
                stream_parts.append(text)

            page.extract_text(
                visitor_operand_before=visitor_operand_before,
                visitor_text=visitor_text,
            )
            text = "".join(stream_parts)
        except DocumentExtractionError:
            raise
        except Exception as exc:
            raise DocumentExtractionError(
                f"PDF text extraction failed on page {page_number}"
            ) from exc
        if text.strip():
            paragraphs.append(text.strip())
    if ignored_boilerplate:
        warnings.append("repeated PDF edge images were treated as page boilerplate and ignored")
    if assets:
        warnings.append(
            "PDF images were placed using content-stream order; complex layouts require review"
        )
    return ExtractedDocument(text="\n".join(paragraphs), assets=assets, warnings=warnings)


def _extract_doc(path: Path) -> ExtractedDocument:
    try:
        result = subprocess.run(
            ["antiword", "-m", "UTF-8.txt", str(path)],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise DocumentExtractionError("legacy DOC extraction is unavailable") from exc
    if result.returncode != 0:
        raise DocumentExtractionError("legacy DOC text extraction failed")
    text = result.stdout.decode("utf-8", errors="replace").strip()
    return ExtractedDocument(
        text=text,
        warnings=["legacy DOC embedded images cannot be recovered; convert to DOCX for image preservation"],
    )


def extract_document(path: Path, mime_type: str | None) -> ExtractedDocument:
    suffix = path.suffix.lower()
    data = path.read_bytes()
    if suffix == ".docx":
        return _extract_docx(data)
    if suffix == ".pdf":
        return _extract_pdf(data)
    if suffix == ".doc":
        return _extract_doc(path)
    if (mime_type or "").startswith("image/"):
        raise DocumentExtractionError(
            "image-only question parsing requires OCR, which is not configured"
        )
    raise DocumentExtractionError("resource format is not supported for question parsing")

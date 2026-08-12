"""Automatic quality checks for rendered paper documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO

from docx import Document
from docx.oxml.ns import qn
from PIL import Image
from pypdf import PdfReader


FOOTER_PATTERN = re.compile(r"第\s*\d+\s*页[，,]\s*共\s*\d+\s*页")
ANSWER_LABEL_PATTERN = re.compile(r"(?:参考)?答案\s*[:：]|解析\s*[:：]")
ORPHAN_SECTION_PATTERN = re.compile(
    r"^[一二三四五六七八九十\d]+[、.]"
    r"(?:单项选择题|多项选择题|判断题|填空题|简答题|综合题)$"
)
ORPHAN_DESCRIPTION_PATTERN = re.compile(r"^本大题共.+分[。.]?$")
ORPHAN_QUESTION_NUMBER_PATTERN = re.compile(r"^\d+[、.]$")
ORPHAN_TEACHER_DETAIL_PATTERN = re.compile(r"^(?:答案|解析|知识点|难度)\s*[:：]")
ORPHAN_OPTION_PATTERN = re.compile(r"^[B-H][.、]\s*")


class DocumentRenderValidationError(RuntimeError):
    """Raised when a rendered document fails its release quality gate."""


@dataclass(frozen=True, slots=True)
class RenderInspectionReport:
    page_count: int
    expected_image_count: int
    rendered_image_count: int
    blank_pages: tuple[int, ...]
    answer_leaks: tuple[str, ...]
    abnormal_break_pages: tuple[int, ...]

    @property
    def passed(self) -> bool:
        return not (
            self.blank_pages
            or self.answer_leaks
            or self.abnormal_break_pages
            or self.rendered_image_count < self.expected_image_count
        )


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _inspect_docx_images(content: bytes) -> int:
    try:
        document = Document(BytesIO(content))
    except Exception as exc:
        raise DocumentRenderValidationError(
            "render check could not open generated DOCX"
        ) from exc

    references = tuple(document._element.iter(qn("a:blip")))
    image_parts = [
        part
        for part in document.part.package.parts
        if part.content_type.startswith("image/")
    ]
    for part in image_parts:
        try:
            with Image.open(BytesIO(part.blob)) as image:
                image.verify()
        except Exception as exc:
            raise DocumentRenderValidationError(
                f"DOCX contains an unreadable image: {part.partname}"
            ) from exc
    if references and not image_parts:
        raise DocumentRenderValidationError(
            "DOCX contains image references without embedded resources"
        )
    return len(references)


def _meaningful_lines(text: str) -> list[str]:
    without_footer = FOOTER_PATTERN.sub("", text)
    return [line.strip() for line in without_footer.splitlines() if line.strip()]


def _find_answer_leaks(
    pdf_text: str,
    *,
    allow_answers: bool,
    protected_texts: tuple[str, ...],
) -> tuple[str, ...]:
    if allow_answers:
        return ()
    leaks: list[str] = []
    label = ANSWER_LABEL_PATTERN.search(pdf_text)
    if label:
        leaks.append(label.group(0))
    normalized_pdf = _normalized_text(pdf_text)
    for value in protected_texts:
        normalized = _normalized_text(value)
        if len(normalized) >= 8 and normalized in normalized_pdf:
            preview = normalized[:40]
            if preview not in leaks:
                leaks.append(preview)
    return tuple(leaks)


def inspect_rendered_document(
    docx_content: bytes,
    pdf_content: bytes,
    *,
    allow_answers: bool,
    protected_texts: tuple[str, ...] = (),
) -> RenderInspectionReport:
    """Inspect the final PDF and reject defects that affect printed papers."""

    expected_images = _inspect_docx_images(docx_content)
    try:
        reader = PdfReader(BytesIO(pdf_content))
        pages = list(reader.pages)
    except Exception as exc:
        raise DocumentRenderValidationError(
            "render check could not open generated PDF"
        ) from exc

    blank_pages: list[int] = []
    abnormal_break_pages: list[int] = []
    rendered_images = 0
    page_texts: list[str] = []
    for page_number, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
            image_count = len(page.images)
        except Exception as exc:
            raise DocumentRenderValidationError(
                f"render check could not inspect PDF page {page_number}"
            ) from exc
        page_texts.append(text)
        rendered_images += image_count
        lines = _meaningful_lines(text)
        if not lines and image_count == 0:
            blank_pages.append(page_number)
            continue
        if lines and (
            ORPHAN_SECTION_PATTERN.fullmatch(lines[-1])
            or ORPHAN_DESCRIPTION_PATTERN.fullmatch(lines[-1])
            or ORPHAN_QUESTION_NUMBER_PATTERN.fullmatch(lines[-1])
            or (
                page_number > 1
                and (
                    ORPHAN_TEACHER_DETAIL_PATTERN.match(lines[0])
                    or (
                        ORPHAN_OPTION_PATTERN.match(lines[0])
                        and not any(line.startswith("A. ") for line in lines)
                    )
                )
            )
        ):
            abnormal_break_pages.append(page_number)

    report = RenderInspectionReport(
        page_count=len(pages),
        expected_image_count=expected_images,
        rendered_image_count=rendered_images,
        blank_pages=tuple(blank_pages),
        answer_leaks=_find_answer_leaks(
            "\n".join(page_texts),
            allow_answers=allow_answers,
            protected_texts=protected_texts,
        ),
        abnormal_break_pages=tuple(abnormal_break_pages),
    )
    issues: list[str] = []
    if report.rendered_image_count < report.expected_image_count:
        issues.append(
            "missing rendered images "
            f"({report.rendered_image_count}/{report.expected_image_count})"
        )
    if report.blank_pages:
        issues.append(f"blank pages: {list(report.blank_pages)}")
    if report.answer_leaks:
        issues.append(f"answer leakage: {list(report.answer_leaks)}")
    if report.abnormal_break_pages:
        issues.append(
            f"abnormal page breaks: {list(report.abnormal_break_pages)}"
        )
    if issues:
        raise DocumentRenderValidationError("; ".join(issues))
    return report


__all__ = [
    "DocumentRenderValidationError",
    "RenderInspectionReport",
    "inspect_rendered_document",
]

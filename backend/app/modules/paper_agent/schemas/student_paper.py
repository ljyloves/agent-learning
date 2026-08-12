"""Contracts for exporting an assembled paper as a student Word document."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.paper_agent.schemas.assembly import PaperAssemblyResult


Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


def normalize_docx_filename(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("filename cannot be blank")
    if any(character in normalized for character in '<>:"/\\|?*'):
        raise ValueError("filename contains unsupported characters")
    return normalized[:-5] if normalized.casefold().endswith(".docx") else normalized


class StudentPaperWordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper: PaperAssemblyResult
    title: Title = "高中生物试卷"
    subtitle: ShortText | None = None
    school_name: ShortText | None = None
    grade_name: ShortText = "高中"
    duration_minutes: int = Field(default=60, ge=1, le=300)
    instructions: list[ShortText] = Field(
        default_factory=lambda: [
            "请在答题区域内作答，超出答题区域的答案无效。",
            "选择题请选出最符合题意的一项。",
        ],
        max_length=10,
    )
    start_each_section_on_new_page: bool = True
    filename: str | None = Field(default=None, max_length=120)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str | None) -> str | None:
        return normalize_docx_filename(value)


class TeacherAnswerWordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper: PaperAssemblyResult
    title: Title = "高中生物试卷答案与解析"
    subtitle: ShortText | None = None
    start_each_section_on_new_page: bool = False
    filename: str | None = Field(default=None, max_length=120)

    _validate_filename = field_validator("filename")(normalize_docx_filename)


class AnswerSheetWordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper: PaperAssemblyResult
    title: Title = "高中生物试卷答题卡"
    subtitle: ShortText | None = None
    school_name: ShortText | None = None
    grade_name: ShortText = "高中"
    filename: str | None = Field(default=None, max_length=120)

    _validate_filename = field_validator("filename")(normalize_docx_filename)

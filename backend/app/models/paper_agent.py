"""SQLAlchemy persistence models for the Paper Agent domain."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PaperJobModel(Base):
    __tablename__ = "paper_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'awaiting_review', "
            "'completed', 'failed', 'cancelled')",
            name="ck_paper_jobs_status",
        ),
        CheckConstraint(
            "(status = 'failed' AND failure_reason IS NOT NULL) OR "
            "(status <> 'failed' AND failure_reason IS NULL)",
            name="ck_paper_jobs_failure_reason",
        ),
        CheckConstraint(
            "review_status IN ('not_started', 'pending', 'approved', "
            "'rejected', 'revision_required')",
            name="ck_paper_jobs_review_status",
        ),
        CheckConstraint(
            "(review_status IN ('approved', 'rejected', 'revision_required') "
            "AND review_result IS NOT NULL) OR "
            "(review_status IN ('not_started', 'pending') "
            "AND review_result IS NULL)",
            name="ck_paper_jobs_review_result",
        ),
    )

    job_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_started",
        server_default=text("'not_started'"),
        index=True,
    )
    review_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class QuestionSourceModel(Base):
    __tablename__ = "question_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('website', 'api', 'file', 'book', 'manual')",
            name="ck_question_sources_type",
        ),
        CheckConstraint(
            "uri IS NOT NULL OR external_id IS NOT NULL",
            name="ck_question_sources_locator",
        ),
    )

    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    uri: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(255))
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    attribution: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(String(255))


class QuestionResourceModel(Base):
    __tablename__ = "question_resources"
    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('image', 'document', 'webpage', 'attachment')",
            name="ck_question_resources_type",
        ),
        CheckConstraint(
            "sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_question_resources_sha256",
        ),
    )

    resource_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("question_sources.source_id"),
        nullable=False,
        index=True,
    )
    mime_type: Mapped[str | None] = mapped_column(String(255))
    sha256: Mapped[str | None] = mapped_column(String(64))


class QuestionModel(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "question_type IN ('single_choice', 'multiple_choice', "
            "'true_false', 'fill_blank', 'short_answer', 'composite')",
            name="ck_questions_type",
        ),
        CheckConstraint("position >= 0", name="ck_questions_position"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    parent_question_id: Mapped[str | None] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("question_sources.source_id"),
        nullable=False,
        index=True,
    )
    question_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    explanation: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class QuestionOptionModel(Base):
    __tablename__ = "question_options"
    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "label",
            name="uq_question_options_question_label",
        ),
        CheckConstraint("position >= 0", name="ck_question_options_position"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )


class QuestionImageModel(Base):
    __tablename__ = "question_images"
    __table_args__ = (
        CheckConstraint(
            "(question_id IS NOT NULL AND option_id IS NULL) OR "
            "(question_id IS NULL AND option_id IS NOT NULL)",
            name="ck_question_images_one_owner",
        ),
        CheckConstraint("position >= 0", name="ck_question_images_position"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("question_resources.resource_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    question_id: Mapped[str | None] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
    )
    option_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_options.id", ondelete="CASCADE"),
        index=True,
    )
    alt_text: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

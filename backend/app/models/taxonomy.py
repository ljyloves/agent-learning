"""SQLAlchemy models for the high-school biology taxonomy."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CurriculumModuleModel(Base):
    __tablename__ = "biology_curriculum_modules"
    __table_args__ = (
        CheckConstraint(
            "course_type IN ('required', 'selective_required')",
            name="ck_biology_curriculum_modules_course_type",
        ),
        CheckConstraint(
            "sort_order > 0",
            name="ck_biology_curriculum_modules_sort_order",
        ),
        UniqueConstraint(
            "sort_order",
            name="uq_biology_curriculum_modules_sort_order",
        ),
    )

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    course_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )


class KnowledgePointModel(Base):
    __tablename__ = "biology_knowledge_points"
    __table_args__ = (
        CheckConstraint(
            "sort_order > 0",
            name="ck_biology_knowledge_points_sort_order",
        ),
        UniqueConstraint(
            "module_code",
            "name",
            name="uq_biology_knowledge_points_module_name",
        ),
        UniqueConstraint(
            "module_code",
            "sort_order",
            name="uq_biology_knowledge_points_module_order",
        ),
    )

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    module_code: Mapped[str] = mapped_column(
        ForeignKey("biology_curriculum_modules.code"),
        nullable=False,
        index=True,
    )
    parent_code: Mapped[str | None] = mapped_column(
        ForeignKey("biology_knowledge_points.code", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )


class CoreCompetencyModel(Base):
    __tablename__ = "biology_core_competencies"
    __table_args__ = (
        CheckConstraint(
            "sort_order > 0",
            name="ck_biology_core_competencies_sort_order",
        ),
        UniqueConstraint(
            "sort_order",
            name="uq_biology_core_competencies_sort_order",
        ),
    )

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )


class PaperJobQuestionModel(Base):
    __tablename__ = "paper_job_questions"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_paper_job_questions_position",
        ),
        UniqueConstraint(
            "job_id",
            "position",
            name="uq_paper_job_questions_job_position",
        ),
    )

    job_id: Mapped[str] = mapped_column(
        ForeignKey("paper_jobs.job_id", ondelete="CASCADE"),
        primary_key=True,
    )
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )


class QuestionKnowledgePointModel(Base):
    __tablename__ = "question_knowledge_points"

    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    knowledge_point_code: Mapped[str] = mapped_column(
        ForeignKey("biology_knowledge_points.code"),
        primary_key=True,
    )


class QuestionCoreCompetencyModel(Base):
    __tablename__ = "question_core_competencies"

    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    competency_code: Mapped[str] = mapped_column(
        ForeignKey("biology_core_competencies.code"),
        primary_key=True,
    )

"""Seed the high-school biology taxonomy.

Revision ID: 20260810_0002
Revises: 20260810_0001
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260810_0002"
down_revision: str | None = "20260810_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MODULES = [
    {
        "code": "BIO-M1",
        "name": "\u5206\u5b50\u4e0e\u7ec6\u80de",
        "course_type": "required",
        "description": "\u4ece\u5206\u5b50\u548c\u7ec6\u80de\u5c42\u6b21\u8ba4\u8bc6\u751f\u547d\u7cfb\u7edf\u7684\u7269\u8d28\u57fa\u7840\u3001\u7ed3\u6784\u57fa\u7840\u548c\u751f\u547d\u6d3b\u52a8\u3002",
        "sort_order": 1,
    },
    {
        "code": "BIO-M2",
        "name": "\u9057\u4f20\u4e0e\u8fdb\u5316",
        "course_type": "required",
        "description": "\u8ba4\u8bc6\u9057\u4f20\u4fe1\u606f\u7684\u4f20\u9012\u3001\u8868\u8fbe\u3001\u53d8\u5f02\u4ee5\u53ca\u751f\u7269\u8fdb\u5316\u7684\u57fa\u672c\u89c4\u5f8b\u3002",
        "sort_order": 2,
    },
    {
        "code": "BIO-M3",
        "name": "\u7a33\u6001\u4e0e\u8c03\u8282",
        "course_type": "selective_required",
        "description": "\u8ba4\u8bc6\u751f\u547d\u7cfb\u7edf\u901a\u8fc7\u8c03\u8282\u7ef4\u6301\u7a33\u6001\u7684\u673a\u5236\u53ca\u5176\u610f\u4e49\u3002",
        "sort_order": 3,
    },
    {
        "code": "BIO-M4",
        "name": "\u751f\u7269\u4e0e\u73af\u5883",
        "course_type": "selective_required",
        "description": "\u4ece\u79cd\u7fa4\u3001\u7fa4\u843d\u548c\u751f\u6001\u7cfb\u7edf\u5c42\u6b21\u8ba4\u8bc6\u751f\u7269\u4e0e\u73af\u5883\u7684\u76f8\u4e92\u4f5c\u7528\u3002",
        "sort_order": 4,
    },
    {
        "code": "BIO-M5",
        "name": "\u751f\u7269\u6280\u672f\u4e0e\u5de5\u7a0b",
        "course_type": "selective_required",
        "description": "\u8ba4\u8bc6\u73b0\u4ee3\u751f\u7269\u6280\u672f\u7684\u539f\u7406\u3001\u5de5\u7a0b\u5b9e\u8df5\u3001\u5e94\u7528\u4ef7\u503c\u4e0e\u4f26\u7406\u8fb9\u754c\u3002",
        "sort_order": 5,
    },
]


KNOWLEDGE_POINTS = [
    ("BIO-M1-K01", "BIO-M1", "\u7ec6\u80de\u7684\u5206\u5b50\u7ec4\u6210", "\u7ec4\u6210\u7ec6\u80de\u7684\u5143\u7d20\u3001\u65e0\u673a\u7269\u548c\u6709\u673a\u7269\u3002", 1),
    ("BIO-M1-K02", "BIO-M1", "\u7ec6\u80de\u57fa\u672c\u7ed3\u6784", "\u7ec6\u80de\u819c\u3001\u7ec6\u80de\u5668\u3001\u7ec6\u80de\u6838\u53ca\u539f\u6838\u4e0e\u771f\u6838\u7ec6\u80de\u3002", 2),
    ("BIO-M1-K03", "BIO-M1", "\u7269\u8d28\u8de8\u819c\u8fd0\u8f93", "\u88ab\u52a8\u8fd0\u8f93\u3001\u4e3b\u52a8\u8fd0\u8f93\u548c\u80de\u541e\u80de\u5410\u3002", 3),
    ("BIO-M1-K04", "BIO-M1", "\u9176\u4e0eATP", "\u9176\u7684\u4f5c\u7528\u4e0e\u7279\u6027\u4ee5\u53caATP\u5728\u80fd\u91cf\u4ee3\u8c22\u4e2d\u7684\u4f5c\u7528\u3002", 4),
    ("BIO-M1-K05", "BIO-M1", "\u7ec6\u80de\u4ee3\u8c22", "\u7ec6\u80de\u547c\u5438\u3001\u5149\u5408\u4f5c\u7528\u53ca\u7269\u8d28\u548c\u80fd\u91cf\u53d8\u5316\u3002", 5),
    ("BIO-M1-K06", "BIO-M1", "\u7ec6\u80de\u589e\u6b96", "\u7ec6\u80de\u5468\u671f\u3001\u6709\u4e1d\u5206\u88c2\u548c\u51cf\u6570\u5206\u88c2\u3002", 6),
    ("BIO-M1-K07", "BIO-M1", "\u7ec6\u80de\u5206\u5316\u4e0e\u751f\u547d\u5386\u7a0b", "\u7ec6\u80de\u5206\u5316\u3001\u5168\u80fd\u6027\u3001\u8870\u8001\u3001\u6b7b\u4ea1\u548c\u764c\u53d8\u3002", 7),
    ("BIO-M2-K01", "BIO-M2", "\u5b5f\u5fb7\u5c14\u9057\u4f20\u89c4\u5f8b", "\u5206\u79bb\u5b9a\u5f8b\u3001\u81ea\u7531\u7ec4\u5408\u5b9a\u5f8b\u53ca\u5176\u5e94\u7528\u3002", 1),
    ("BIO-M2-K02", "BIO-M2", "\u67d3\u8272\u4f53\u4e0e\u4f34\u6027\u9057\u4f20", "\u57fa\u56e0\u4e0e\u67d3\u8272\u4f53\u5173\u7cfb\u3001\u4f34\u6027\u9057\u4f20\u548c\u9057\u4f20\u7cfb\u8c31\u3002", 2),
    ("BIO-M2-K03", "BIO-M2", "DNA\u7ed3\u6784\u4e0e\u590d\u5236", "DNA\u7ed3\u6784\u3001\u590d\u5236\u8fc7\u7a0b\u53ca\u9057\u4f20\u4fe1\u606f\u7a33\u5b9a\u4f20\u9012\u3002", 3),
    ("BIO-M2-K04", "BIO-M2", "\u57fa\u56e0\u8868\u8fbe", "\u8f6c\u5f55\u3001\u7ffb\u8bd1\u53ca\u57fa\u56e0\u8868\u8fbe\u8c03\u63a7\u3002", 4),
    ("BIO-M2-K05", "BIO-M2", "\u751f\u7269\u53d8\u5f02", "\u57fa\u56e0\u7a81\u53d8\u3001\u57fa\u56e0\u91cd\u7ec4\u3001\u67d3\u8272\u4f53\u53d8\u5f02\u53ca\u80b2\u79cd\u3002", 5),
    ("BIO-M2-K06", "BIO-M2", "\u751f\u7269\u8fdb\u5316", "\u81ea\u7136\u9009\u62e9\u3001\u79cd\u7fa4\u57fa\u56e0\u9891\u7387\u3001\u7269\u79cd\u5f62\u6210\u548c\u5171\u540c\u8fdb\u5316\u3002", 6),
    ("BIO-M3-K01", "BIO-M3", "\u5185\u73af\u5883\u4e0e\u7a33\u6001", "\u5185\u73af\u5883\u7ec4\u6210\u3001\u7406\u5316\u6027\u8d28\u53ca\u7a33\u6001\u8c03\u8282\u7f51\u7edc\u3002", 1),
    ("BIO-M3-K02", "BIO-M3", "\u795e\u7ecf\u8c03\u8282", "\u795e\u7ecf\u7cfb\u7edf\u7ed3\u6784\u3001\u53cd\u5c04\u3001\u5174\u594b\u4f20\u5bfc\u548c\u9ad8\u7ea7\u795e\u7ecf\u6d3b\u52a8\u3002", 2),
    ("BIO-M3-K03", "BIO-M3", "\u4f53\u6db2\u8c03\u8282", "\u6fc0\u7d20\u8c03\u8282\u3001\u53cd\u9988\u8c03\u8282\u53ca\u795e\u7ecf\u4e0e\u4f53\u6db2\u8c03\u8282\u5173\u7cfb\u3002", 3),
    ("BIO-M3-K04", "BIO-M3", "\u514d\u75ab\u8c03\u8282", "\u514d\u75ab\u7cfb\u7edf\u7ec4\u6210\u3001\u7279\u5f02\u6027\u514d\u75ab\u548c\u514d\u75ab\u529f\u80fd\u5f02\u5e38\u3002", 4),
    ("BIO-M3-K05", "BIO-M3", "\u690d\u7269\u6fc0\u7d20\u8c03\u8282", "\u690d\u7269\u6fc0\u7d20\u7684\u4f5c\u7528\u3001\u76f8\u4e92\u5173\u7cfb\u53ca\u751f\u4ea7\u5e94\u7528\u3002", 5),
    ("BIO-M3-K06", "BIO-M3", "\u690d\u7269\u751f\u547d\u6d3b\u52a8\u7684\u73af\u5883\u8c03\u8282", "\u5149\u3001\u6e29\u5ea6\u548c\u91cd\u529b\u7b49\u73af\u5883\u56e0\u7d20\u5bf9\u690d\u7269\u751f\u547d\u6d3b\u52a8\u7684\u8c03\u8282\u3002", 6),
    ("BIO-M4-K01", "BIO-M4", "\u79cd\u7fa4\u53ca\u5176\u52a8\u6001", "\u79cd\u7fa4\u6570\u91cf\u7279\u5f81\u3001\u589e\u957f\u6a21\u578b\u548c\u6570\u91cf\u53d8\u5316\u56e0\u7d20\u3002", 1),
    ("BIO-M4-K02", "BIO-M4", "\u7fa4\u843d\u7ed3\u6784\u4e0e\u6f14\u66ff", "\u7fa4\u843d\u7ec4\u6210\u3001\u79cd\u95f4\u5173\u7cfb\u3001\u7a7a\u95f4\u7ed3\u6784\u548c\u6f14\u66ff\u3002", 2),
    ("BIO-M4-K03", "BIO-M4", "\u751f\u6001\u7cfb\u7edf\u7ed3\u6784", "\u751f\u6001\u7cfb\u7edf\u7ec4\u6210\u6210\u5206\u3001\u8425\u517b\u7ed3\u6784\u548c\u98df\u7269\u7f51\u3002", 3),
    ("BIO-M4-K04", "BIO-M4", "\u751f\u6001\u7cfb\u7edf\u8fc7\u7a0b", "\u80fd\u91cf\u6d41\u52a8\u3001\u7269\u8d28\u5faa\u73af\u548c\u4fe1\u606f\u4f20\u9012\u3002", 4),
    ("BIO-M4-K05", "BIO-M4", "\u751f\u6001\u7cfb\u7edf\u7a33\u5b9a\u6027", "\u751f\u6001\u5e73\u8861\u3001\u7a33\u5b9a\u6027\u673a\u5236\u548c\u751f\u6001\u5de5\u7a0b\u3002", 5),
    ("BIO-M4-K06", "BIO-M4", "\u751f\u7269\u591a\u6837\u6027\u4e0e\u4fdd\u62a4", "\u751f\u7269\u591a\u6837\u6027\u7684\u4ef7\u503c\u3001\u5a01\u80c1\u548c\u4fdd\u62a4\u63aa\u65bd\u3002", 6),
    ("BIO-M5-K01", "BIO-M5", "\u4f20\u7edf\u53d1\u9175\u6280\u672f", "\u53d1\u9175\u539f\u7406\u4ee5\u53ca\u679c\u9152\u3001\u679c\u918b\u548c\u6ce1\u83dc\u7b49\u5236\u4f5c\u3002", 1),
    ("BIO-M5-K02", "BIO-M5", "\u5fae\u751f\u7269\u57f9\u517b\u4e0e\u5e94\u7528", "\u65e0\u83cc\u6280\u672f\u3001\u57f9\u517b\u57fa\u3001\u5206\u79bb\u8ba1\u6570\u548c\u83cc\u79cd\u5229\u7528\u3002", 2),
    ("BIO-M5-K03", "BIO-M5", "\u690d\u7269\u7ec6\u80de\u5de5\u7a0b", "\u690d\u7269\u7ec4\u7ec7\u57f9\u517b\u3001\u4f53\u7ec6\u80de\u6742\u4ea4\u548c\u7ec6\u80de\u4ea7\u7269\u5236\u5907\u3002", 3),
    ("BIO-M5-K04", "BIO-M5", "\u52a8\u7269\u7ec6\u80de\u5de5\u7a0b", "\u52a8\u7269\u7ec6\u80de\u57f9\u517b\u3001\u6838\u79fb\u690d\u3001\u514b\u9686\u548c\u5355\u514b\u9686\u6297\u4f53\u3002", 4),
    ("BIO-M5-K05", "BIO-M5", "\u57fa\u56e0\u4e0e\u86cb\u767d\u8d28\u5de5\u7a0b", "\u57fa\u56e0\u5de5\u7a0b\u5de5\u5177\u3001\u57fa\u672c\u64cd\u4f5c\u7a0b\u5e8f\u53ca\u86cb\u767d\u8d28\u5de5\u7a0b\u3002", 5),
    ("BIO-M5-K06", "BIO-M5", "\u80da\u80ce\u5de5\u7a0b", "\u4f53\u5916\u53d7\u7cbe\u3001\u65e9\u671f\u80da\u80ce\u57f9\u517b\u3001\u80da\u80ce\u79fb\u690d\u548c\u5206\u5272\u3002", 6),
    ("BIO-M5-K07", "BIO-M5", "\u751f\u7269\u6280\u672f\u5b89\u5168\u4e0e\u4f26\u7406", "\u8f6c\u57fa\u56e0\u5b89\u5168\u3001\u751f\u7269\u6b66\u5668\u3001\u514b\u9686\u4f26\u7406\u548c\u6280\u672f\u6cbb\u7406\u3002", 7),
]


CORE_COMPETENCIES = [
    {
        "code": "BIO-C1",
        "name": "\u751f\u547d\u89c2\u5ff5",
        "description": "\u8fd0\u7528\u7ed3\u6784\u4e0e\u529f\u80fd\u3001\u8fdb\u5316\u4e0e\u9002\u5e94\u3001\u7a33\u6001\u4e0e\u5e73\u8861\u3001\u7269\u8d28\u4e0e\u80fd\u91cf\u7b49\u89c2\u5ff5\u89e3\u91ca\u751f\u547d\u73b0\u8c61\u3002",
        "sort_order": 1,
    },
    {
        "code": "BIO-C2",
        "name": "\u79d1\u5b66\u601d\u7ef4",
        "description": "\u57fa\u4e8e\u4e8b\u5b9e\u548c\u8bc1\u636e\uff0c\u8fd0\u7528\u5f52\u7eb3\u3001\u6f14\u7ece\u3001\u5efa\u6a21\u3001\u6279\u5224\u6027\u601d\u7ef4\u7b49\u65b9\u6cd5\u8ba4\u8bc6\u751f\u547d\u89c4\u5f8b\u3002",
        "sort_order": 2,
    },
    {
        "code": "BIO-C3",
        "name": "\u79d1\u5b66\u63a2\u7a76",
        "description": "\u63d0\u51fa\u95ee\u9898\u3001\u4f5c\u51fa\u5047\u8bbe\u3001\u8bbe\u8ba1\u5b9e\u9a8c\u3001\u83b7\u53d6\u8bc1\u636e\u5e76\u4ea4\u6d41\u8bc4\u4ef7\u63a2\u7a76\u7ed3\u8bba\u3002",
        "sort_order": 3,
    },
    {
        "code": "BIO-C4",
        "name": "\u793e\u4f1a\u8d23\u4efb",
        "description": "\u5173\u6ce8\u5065\u5eb7\u3001\u751f\u6001\u4e0e\u751f\u7269\u6280\u672f\u8bae\u9898\uff0c\u57fa\u4e8e\u751f\u7269\u5b66\u77e5\u8bc6\u4f5c\u51fa\u8d1f\u8d23\u4efb\u7684\u5224\u65ad\u548c\u884c\u52a8\u3002",
        "sort_order": 4,
    },
]


def upgrade() -> None:
    modules = op.create_table(
        "biology_curriculum_modules",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("course_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "course_type IN ('required', 'selective_required')",
            name="ck_biology_curriculum_modules_course_type",
        ),
        sa.CheckConstraint(
            "sort_order > 0",
            name="ck_biology_curriculum_modules_sort_order",
        ),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint(
            "sort_order",
            name="uq_biology_curriculum_modules_sort_order",
        ),
    )

    knowledge_points = op.create_table(
        "biology_knowledge_points",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("module_code", sa.String(length=32), nullable=False),
        sa.Column("parent_code", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sort_order > 0",
            name="ck_biology_knowledge_points_sort_order",
        ),
        sa.ForeignKeyConstraint(
            ["module_code"],
            ["biology_curriculum_modules.code"],
        ),
        sa.ForeignKeyConstraint(
            ["parent_code"],
            ["biology_knowledge_points.code"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint(
            "module_code",
            "name",
            name="uq_biology_knowledge_points_module_name",
        ),
        sa.UniqueConstraint(
            "module_code",
            "sort_order",
            name="uq_biology_knowledge_points_module_order",
        ),
    )
    op.create_index(
        "ix_biology_knowledge_points_module_code",
        "biology_knowledge_points",
        ["module_code"],
    )
    op.create_index(
        "ix_biology_knowledge_points_parent_code",
        "biology_knowledge_points",
        ["parent_code"],
    )

    competencies = op.create_table(
        "biology_core_competencies",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sort_order > 0",
            name="ck_biology_core_competencies_sort_order",
        ),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint(
            "sort_order",
            name="uq_biology_core_competencies_sort_order",
        ),
    )

    op.create_table(
        "paper_job_questions",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_paper_job_questions_position",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["paper_jobs.job_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("job_id", "question_id"),
        sa.UniqueConstraint(
            "job_id",
            "position",
            name="uq_paper_job_questions_job_position",
        ),
    )

    op.create_table(
        "question_knowledge_points",
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_point_code", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["knowledge_point_code"],
            ["biology_knowledge_points.code"],
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("question_id", "knowledge_point_code"),
    )

    op.create_table(
        "question_core_competencies",
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("competency_code", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["competency_code"],
            ["biology_core_competencies.code"],
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("question_id", "competency_code"),
    )

    op.bulk_insert(modules, MODULES)
    op.bulk_insert(
        knowledge_points,
        [
            {
                "code": code,
                "module_code": module_code,
                "parent_code": None,
                "name": name,
                "description": description,
                "sort_order": sort_order,
            }
            for code, module_code, name, description, sort_order in KNOWLEDGE_POINTS
        ],
    )
    op.bulk_insert(competencies, CORE_COMPETENCIES)


def downgrade() -> None:
    op.drop_table("question_core_competencies")
    op.drop_table("question_knowledge_points")
    op.drop_table("paper_job_questions")
    op.drop_table("biology_core_competencies")
    op.drop_table("biology_knowledge_points")
    op.drop_table("biology_curriculum_modules")

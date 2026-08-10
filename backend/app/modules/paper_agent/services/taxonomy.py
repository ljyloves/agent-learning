"""Read services for the high-school biology taxonomy."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CoreCompetencyModel,
    CurriculumModuleModel,
    KnowledgePointModel,
)
from app.modules.paper_agent.schemas.taxonomy import (
    BiologyTaxonomyResponse,
    CoreCompetencyRead,
    CurriculumModuleRead,
    KnowledgePointRead,
)


async def get_biology_taxonomy(
    session: AsyncSession,
) -> BiologyTaxonomyResponse:
    modules = list(
        await session.scalars(
            select(CurriculumModuleModel)
            .where(CurriculumModuleModel.is_active.is_(True))
            .order_by(CurriculumModuleModel.sort_order)
        )
    )
    knowledge_points = list(
        await session.scalars(
            select(KnowledgePointModel)
            .where(KnowledgePointModel.is_active.is_(True))
            .order_by(
                KnowledgePointModel.module_code,
                KnowledgePointModel.sort_order,
            )
        )
    )
    competencies = list(
        await session.scalars(
            select(CoreCompetencyModel)
            .where(CoreCompetencyModel.is_active.is_(True))
            .order_by(CoreCompetencyModel.sort_order)
        )
    )

    points_by_module: dict[str, list[KnowledgePointRead]] = defaultdict(list)
    for point in knowledge_points:
        points_by_module[point.module_code].append(
            KnowledgePointRead.model_validate(point)
        )

    return BiologyTaxonomyResponse(
        modules=[
            CurriculumModuleRead(
                code=module.code,
                name=module.name,
                course_type=module.course_type,
                description=module.description,
                sort_order=module.sort_order,
                knowledge_points=points_by_module[module.code],
            )
            for module in modules
        ],
        core_competencies=[
            CoreCompetencyRead.model_validate(competency)
            for competency in competencies
        ],
    )

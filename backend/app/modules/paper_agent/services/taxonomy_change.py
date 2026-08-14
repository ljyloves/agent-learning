"""Previewed and transactional maintenance for the biology taxonomy."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    CurriculumModuleModel,
    KnowledgePointModel,
    QuestionKnowledgePointModel,
)
from app.modules.paper_agent.schemas.taxonomy_change import (
    TaxonomyChangeAction,
    TaxonomyChangePreview,
    TaxonomyChangeRequest,
    TaxonomyChangeResult,
    TaxonomyEntityType,
    TaxonomyItemSnapshot,
)


class TaxonomyChangeConflictError(ValueError):
    pass


class TaxonomyWriteDisabledError(PermissionError):
    pass


def _module_snapshot(model: CurriculumModuleModel) -> TaxonomyItemSnapshot:
    return TaxonomyItemSnapshot(
        entity_type=TaxonomyEntityType.MODULE,
        code=model.code,
        name=model.name,
        description=model.description,
        course_type=model.course_type,
        sort_order=model.sort_order,
        is_active=model.is_active,
    )


def _point_snapshot(model: KnowledgePointModel) -> TaxonomyItemSnapshot:
    return TaxonomyItemSnapshot(
        entity_type=TaxonomyEntityType.KNOWLEDGE_POINT,
        code=model.code,
        name=model.name,
        description=model.description,
        module_code=model.module_code,
        parent_code=model.parent_code,
        sort_order=model.sort_order,
        is_active=model.is_active,
    )


async def _next_module_order(session: AsyncSession) -> int:
    current = await session.scalar(select(func.max(CurriculumModuleModel.sort_order)))
    return (current or 0) + 1


async def _next_point_order(session: AsyncSession, module_code: str) -> int:
    current = await session.scalar(
        select(func.max(KnowledgePointModel.sort_order)).where(
            KnowledgePointModel.module_code == module_code
        )
    )
    return (current or 0) + 1


async def _validate_parent(
    session: AsyncSession,
    *,
    target_code: str,
    module_code: str,
    parent_code: str | None,
    blockers: list[str],
) -> None:
    if parent_code is None:
        return
    parent = await session.get(KnowledgePointModel, parent_code)
    if parent is None or not parent.is_active:
        blockers.append(f"父知识点 {parent_code} 不存在或已停用。")
        return
    if parent.module_code != module_code:
        blockers.append("父知识点必须与当前知识点属于同一课程模块。")
        return
    visited: set[str] = set()
    current = parent
    while current is not None and current.code not in visited:
        if current.code == target_code:
            blockers.append("父子关系会形成层级循环。")
            return
        visited.add(current.code)
        current = (
            await session.get(KnowledgePointModel, current.parent_code)
            if current.parent_code
            else None
        )


async def _preview_module_change(
    session: AsyncSession,
    change: TaxonomyChangeRequest,
) -> TaxonomyChangePreview:
    existing = await session.get(CurriculumModuleModel, change.code)
    before = _module_snapshot(existing) if existing is not None else None
    blockers: list[str] = []
    notices: list[str] = []
    after: TaxonomyItemSnapshot | None = None

    if change.action == TaxonomyChangeAction.CREATE_MODULE:
        if existing is not None:
            blockers.append(f"模块编码 {change.code} 已存在。")
        duplicate_name = await session.scalar(
            select(CurriculumModuleModel.code).where(
                CurriculumModuleModel.name == change.name
            )
        )
        if duplicate_name is not None:
            blockers.append(f"模块名称 {change.name} 已被 {duplicate_name} 使用。")
        order = change.sort_order or await _next_module_order(session)
        duplicate_order = await session.scalar(
            select(CurriculumModuleModel.code).where(
                CurriculumModuleModel.sort_order == order
            )
        )
        if duplicate_order is not None:
            blockers.append(f"模块排序 {order} 已被 {duplicate_order} 使用。")
        after = TaxonomyItemSnapshot(
            entity_type=TaxonomyEntityType.MODULE,
            code=change.code,
            name=change.name or "",
            description=change.description or "",
            course_type=change.course_type,
            sort_order=order,
            is_active=True,
        )
        if change.sort_order is None:
            notices.append(f"未指定排序，系统将自动使用 {order}。")

    elif change.action == TaxonomyChangeAction.UPDATE_MODULE:
        if existing is None:
            blockers.append(f"模块 {change.code} 不存在。")
        elif not existing.is_active:
            blockers.append(f"模块 {change.code} 已停用，当前不支持直接修改。")
        else:
            name = change.name or existing.name
            order = change.sort_order or existing.sort_order
            duplicate_name = await session.scalar(
                select(CurriculumModuleModel.code).where(
                    CurriculumModuleModel.name == name,
                    CurriculumModuleModel.code != change.code,
                )
            )
            duplicate_order = await session.scalar(
                select(CurriculumModuleModel.code).where(
                    CurriculumModuleModel.sort_order == order,
                    CurriculumModuleModel.code != change.code,
                )
            )
            if duplicate_name is not None:
                blockers.append(f"模块名称 {name} 已被 {duplicate_name} 使用。")
            if duplicate_order is not None:
                blockers.append(f"模块排序 {order} 已被 {duplicate_order} 使用。")
            after = TaxonomyItemSnapshot(
                entity_type=TaxonomyEntityType.MODULE,
                code=existing.code,
                name=name,
                description=change.description or existing.description,
                course_type=change.course_type or existing.course_type,
                sort_order=order,
                is_active=True,
            )

    else:
        if existing is None:
            blockers.append(f"模块 {change.code} 不存在。")
        elif not existing.is_active:
            blockers.append(f"模块 {change.code} 已经停用。")
        else:
            active_points = await session.scalar(
                select(func.count())
                .select_from(KnowledgePointModel)
                .where(
                    KnowledgePointModel.module_code == change.code,
                    KnowledgePointModel.is_active.is_(True),
                )
            )
            if active_points:
                blockers.append(
                    f"模块仍包含 {active_points} 个启用知识点，请先处理这些知识点。"
                )
            after = before.model_copy(update={"is_active": False})

    return TaxonomyChangePreview(
        action=change.action,
        valid=not blockers,
        before=before,
        after=after,
        notices=notices,
        blockers=blockers,
    )


async def _preview_point_change(
    session: AsyncSession,
    change: TaxonomyChangeRequest,
) -> TaxonomyChangePreview:
    existing = await session.get(KnowledgePointModel, change.code)
    before = _point_snapshot(existing) if existing is not None else None
    blockers: list[str] = []
    notices: list[str] = []
    after: TaxonomyItemSnapshot | None = None

    if change.action == TaxonomyChangeAction.CREATE_KNOWLEDGE_POINT:
        module = await session.get(CurriculumModuleModel, change.module_code)
        if existing is not None:
            blockers.append(f"知识点编码 {change.code} 已存在。")
        if module is None or not module.is_active:
            blockers.append(f"所属模块 {change.module_code} 不存在或已停用。")
        duplicate_name = await session.scalar(
            select(KnowledgePointModel.code).where(
                KnowledgePointModel.module_code == change.module_code,
                KnowledgePointModel.name == change.name,
            )
        )
        if duplicate_name is not None:
            blockers.append(f"同一模块中已存在同名知识点 {duplicate_name}。")
        order = change.sort_order or await _next_point_order(
            session, change.module_code or ""
        )
        duplicate_order = await session.scalar(
            select(KnowledgePointModel.code).where(
                KnowledgePointModel.module_code == change.module_code,
                KnowledgePointModel.sort_order == order,
            )
        )
        if duplicate_order is not None:
            blockers.append(f"知识点排序 {order} 已被 {duplicate_order} 使用。")
        await _validate_parent(
            session,
            target_code=change.code,
            module_code=change.module_code or "",
            parent_code=change.parent_code,
            blockers=blockers,
        )
        after = TaxonomyItemSnapshot(
            entity_type=TaxonomyEntityType.KNOWLEDGE_POINT,
            code=change.code,
            name=change.name or "",
            description=change.description or "",
            module_code=change.module_code,
            parent_code=change.parent_code,
            sort_order=order,
            is_active=True,
        )
        if change.sort_order is None:
            notices.append(f"未指定排序，系统将自动使用 {order}。")

    elif change.action == TaxonomyChangeAction.UPDATE_KNOWLEDGE_POINT:
        if existing is None:
            blockers.append(f"知识点 {change.code} 不存在。")
        elif not existing.is_active:
            blockers.append(f"知识点 {change.code} 已停用，当前不支持直接修改。")
        else:
            module_code = change.module_code or existing.module_code
            module = await session.get(CurriculumModuleModel, module_code)
            if module is None or not module.is_active:
                blockers.append(f"所属模块 {module_code} 不存在或已停用。")
            if change.parent_code is not None:
                parent_code = change.parent_code
            elif change.clear_parent:
                parent_code = None
            else:
                parent_code = existing.parent_code
            if module_code != existing.module_code and change.sort_order is None:
                order = await _next_point_order(session, module_code)
                notices.append(f"知识点移动到新模块后，排序将自动调整为 {order}。")
            else:
                order = change.sort_order or existing.sort_order
            name = change.name or existing.name
            duplicate_name = await session.scalar(
                select(KnowledgePointModel.code).where(
                    KnowledgePointModel.module_code == module_code,
                    KnowledgePointModel.name == name,
                    KnowledgePointModel.code != change.code,
                )
            )
            duplicate_order = await session.scalar(
                select(KnowledgePointModel.code).where(
                    KnowledgePointModel.module_code == module_code,
                    KnowledgePointModel.sort_order == order,
                    KnowledgePointModel.code != change.code,
                )
            )
            if duplicate_name is not None:
                blockers.append(f"同一模块中已存在同名知识点 {duplicate_name}。")
            if duplicate_order is not None:
                blockers.append(f"知识点排序 {order} 已被 {duplicate_order} 使用。")
            await _validate_parent(
                session,
                target_code=change.code,
                module_code=module_code,
                parent_code=parent_code,
                blockers=blockers,
            )
            after = TaxonomyItemSnapshot(
                entity_type=TaxonomyEntityType.KNOWLEDGE_POINT,
                code=existing.code,
                name=name,
                description=change.description or existing.description,
                module_code=module_code,
                parent_code=parent_code,
                sort_order=order,
                is_active=True,
            )

    else:
        if existing is None:
            blockers.append(f"知识点 {change.code} 不存在。")
        elif not existing.is_active:
            blockers.append(f"知识点 {change.code} 已经停用。")
        else:
            active_children = await session.scalar(
                select(func.count())
                .select_from(KnowledgePointModel)
                .where(
                    KnowledgePointModel.parent_code == change.code,
                    KnowledgePointModel.is_active.is_(True),
                )
            )
            if active_children:
                blockers.append(
                    f"知识点仍包含 {active_children} 个启用子知识点，请先处理子节点。"
                )
            references = await session.scalar(
                select(func.count())
                .select_from(QuestionKnowledgePointModel)
                .where(
                    QuestionKnowledgePointModel.knowledge_point_code == change.code
                )
            )
            if references:
                notices.append(
                    f"已有 {references} 道题引用该知识点；停用后历史引用会保留。"
                )
            after = before.model_copy(update={"is_active": False})

    return TaxonomyChangePreview(
        action=change.action,
        valid=not blockers,
        before=before,
        after=after,
        notices=notices,
        blockers=blockers,
    )


async def preview_taxonomy_change(
    session: AsyncSession,
    change: TaxonomyChangeRequest,
) -> TaxonomyChangePreview:
    if change.entity_type == TaxonomyEntityType.MODULE:
        return await _preview_module_change(session, change)
    return await _preview_point_change(session, change)


async def _lock_existing_target(
    session: AsyncSession,
    change: TaxonomyChangeRequest,
) -> None:
    if change.action in {
        TaxonomyChangeAction.CREATE_MODULE,
        TaxonomyChangeAction.CREATE_KNOWLEDGE_POINT,
    }:
        return
    model = (
        CurriculumModuleModel
        if change.entity_type == TaxonomyEntityType.MODULE
        else KnowledgePointModel
    )
    await session.scalar(
        select(model).where(model.code == change.code).with_for_update()
    )


async def apply_taxonomy_change(
    session: AsyncSession,
    change: TaxonomyChangeRequest,
) -> TaxonomyChangeResult:
    if not settings.paper_agent_taxonomy_write_enabled:
        raise TaxonomyWriteDisabledError(
            "taxonomy writes are disabled; enable PAPER_AGENT_TAXONOMY_WRITE_ENABLED"
        )
    await _lock_existing_target(session, change)
    preview = await preview_taxonomy_change(session, change)
    if not preview.valid or preview.after is None:
        raise TaxonomyChangeConflictError("；".join(preview.blockers))

    after = preview.after
    if change.action == TaxonomyChangeAction.CREATE_MODULE:
        model = CurriculumModuleModel(
            code=after.code,
            name=after.name,
            description=after.description,
            course_type=after.course_type,
            sort_order=after.sort_order,
            is_active=True,
        )
        session.add(model)
    elif change.action == TaxonomyChangeAction.CREATE_KNOWLEDGE_POINT:
        model = KnowledgePointModel(
            code=after.code,
            name=after.name,
            description=after.description,
            module_code=after.module_code,
            parent_code=after.parent_code,
            sort_order=after.sort_order,
            is_active=True,
        )
        session.add(model)
    elif change.entity_type == TaxonomyEntityType.MODULE:
        model = await session.get(CurriculumModuleModel, change.code)
        model.name = after.name
        model.description = after.description
        model.course_type = after.course_type
        model.sort_order = after.sort_order
        model.is_active = after.is_active
    else:
        model = await session.get(KnowledgePointModel, change.code)
        model.name = after.name
        model.description = after.description
        model.module_code = after.module_code
        model.parent_code = after.parent_code
        model.sort_order = after.sort_order
        model.is_active = after.is_active

    await session.flush()
    item = _module_snapshot(model) if change.entity_type == TaxonomyEntityType.MODULE else _point_snapshot(model)
    verb = "已停用" if not item.is_active else ("已新增" if preview.before is None else "已更新")
    return TaxonomyChangeResult(
        action=change.action,
        applied=True,
        before=preview.before,
        item=item,
        notices=preview.notices,
        message=f"{verb}{'模块' if item.entity_type == TaxonomyEntityType.MODULE else '知识点'} {item.code} {item.name}。",
    )


__all__ = [
    "TaxonomyChangeConflictError",
    "TaxonomyWriteDisabledError",
    "apply_taxonomy_change",
    "preview_taxonomy_change",
]

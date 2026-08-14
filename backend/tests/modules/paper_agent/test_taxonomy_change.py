import unittest
import uuid
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import CurriculumModuleModel, KnowledgePointModel
from app.modules.paper_agent.schemas.taxonomy_change import (
    TaxonomyChangeAction,
    TaxonomyChangeRequest,
)
from app.modules.paper_agent.services.taxonomy_change import (
    TaxonomyWriteDisabledError,
    apply_taxonomy_change,
    preview_taxonomy_change,
)


class TaxonomyChangeSchemaTests(unittest.IsolatedAsyncioTestCase):
    def test_create_requires_explicit_descriptive_fields(self):
        with self.assertRaises(ValidationError):
            TaxonomyChangeRequest(
                action=TaxonomyChangeAction.CREATE_MODULE,
                code="BIO-M6",
                name="实验拓展",
                course_type="selective_required",
            )

    def test_module_cannot_have_parent(self):
        with self.assertRaises(ValidationError):
            TaxonomyChangeRequest(
                action=TaxonomyChangeAction.CREATE_MODULE,
                code="BIO-M6",
                name="实验拓展",
                description="校本实验拓展模块。",
                course_type="selective_required",
                parent_code="BIO-M1-K01",
            )

    async def test_write_switch_is_closed_by_default(self):
        change = TaxonomyChangeRequest(
            action=TaxonomyChangeAction.CREATE_MODULE,
            code="BIO-M6",
            name="实验拓展",
            description="校本实验拓展模块。",
            course_type="selective_required",
        )
        with (
            patch.object(settings, "paper_agent_taxonomy_write_enabled", False),
            self.assertRaises(TaxonomyWriteDisabledError),
        ):
            await apply_taxonomy_change(AsyncMock(), change)


class TaxonomyChangeServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        suffix = uuid.uuid4().hex[:8].upper()
        self.module_code = f"T52M{suffix}"
        self.root_code = f"T52R{suffix}"
        self.child_code = f"T52C{suffix}"

    async def asyncTearDown(self):
        async with self.sessions() as session:
            await session.execute(
                delete(KnowledgePointModel).where(
                    KnowledgePointModel.code.in_([self.root_code, self.child_code])
                )
            )
            await session.execute(
                delete(CurriculumModuleModel).where(
                    CurriculumModuleModel.code == self.module_code
                )
            )
            await session.commit()
        await self.engine.dispose()

    async def _apply(self, change: TaxonomyChangeRequest):
        async with self.sessions() as session:
            with patch.object(settings, "paper_agent_taxonomy_write_enabled", True):
                result = await apply_taxonomy_change(session, change)
                await session.commit()
                return result

    async def _create_fixture(self):
        await self._apply(
            TaxonomyChangeRequest(
                action=TaxonomyChangeAction.CREATE_MODULE,
                code=self.module_code,
                name=f"BIO-052测试模块-{self.module_code}",
                description="用于验证对话式标签维护。",
                course_type="selective_required",
            )
        )
        await self._apply(
            TaxonomyChangeRequest(
                action=TaxonomyChangeAction.CREATE_KNOWLEDGE_POINT,
                code=self.root_code,
                name="BIO-052测试根知识点",
                description="用于验证层级关系。",
                module_code=self.module_code,
            )
        )
        await self._apply(
            TaxonomyChangeRequest(
                action=TaxonomyChangeAction.CREATE_KNOWLEDGE_POINT,
                code=self.child_code,
                name="BIO-052测试子知识点",
                description="用于验证子节点停用约束。",
                module_code=self.module_code,
                parent_code=self.root_code,
            )
        )

    async def test_create_module_and_hierarchical_points(self):
        await self._create_fixture()

        async with self.sessions() as session:
            module = await session.get(CurriculumModuleModel, self.module_code)
            child = await session.get(KnowledgePointModel, self.child_code)
            duplicate = await preview_taxonomy_change(
                session,
                TaxonomyChangeRequest(
                    action=TaxonomyChangeAction.CREATE_KNOWLEDGE_POINT,
                    code=f"T52D{uuid.uuid4().hex[:8].upper()}",
                    name="BIO-052测试子知识点",
                    description="重复名称。",
                    module_code=self.module_code,
                ),
            )

        self.assertTrue(module.is_active)
        self.assertEqual(child.parent_code, self.root_code)
        self.assertFalse(duplicate.valid)
        self.assertTrue(any("同名知识点" in item for item in duplicate.blockers))

    async def test_cycle_and_active_children_are_blocked(self):
        await self._create_fixture()

        async with self.sessions() as session:
            cycle = await preview_taxonomy_change(
                session,
                TaxonomyChangeRequest(
                    action=TaxonomyChangeAction.UPDATE_KNOWLEDGE_POINT,
                    code=self.root_code,
                    parent_code=self.child_code,
                ),
            )
            deactivate_root = await preview_taxonomy_change(
                session,
                TaxonomyChangeRequest(
                    action=TaxonomyChangeAction.DEACTIVATE_KNOWLEDGE_POINT,
                    code=self.root_code,
                    reason="课程调整。",
                ),
            )
            deactivate_module = await preview_taxonomy_change(
                session,
                TaxonomyChangeRequest(
                    action=TaxonomyChangeAction.DEACTIVATE_MODULE,
                    code=self.module_code,
                    reason="课程调整。",
                ),
            )

        self.assertFalse(cycle.valid)
        self.assertTrue(any("层级循环" in item for item in cycle.blockers))
        self.assertFalse(deactivate_root.valid)
        self.assertTrue(any("子知识点" in item for item in deactivate_root.blockers))
        self.assertFalse(deactivate_module.valid)
        self.assertTrue(any("启用知识点" in item for item in deactivate_module.blockers))

    async def test_leaf_can_be_deactivated_without_deletion(self):
        await self._create_fixture()
        result = await self._apply(
            TaxonomyChangeRequest(
                action=TaxonomyChangeAction.DEACTIVATE_KNOWLEDGE_POINT,
                code=self.child_code,
                reason="合并到上级知识点。",
            )
        )

        async with self.sessions() as session:
            stored = await session.get(KnowledgePointModel, self.child_code)

        self.assertTrue(result.applied)
        self.assertFalse(result.item.is_active)
        self.assertIsNotNone(stored)
        self.assertFalse(stored.is_active)


if __name__ == "__main__":
    unittest.main()

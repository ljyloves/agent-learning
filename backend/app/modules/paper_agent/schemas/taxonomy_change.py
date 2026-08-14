"""Validated contracts for conversational biology taxonomy maintenance."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


TaxonomyCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=32,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    ),
]
TaxonomyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]


class TaxonomyEntityType(StrEnum):
    MODULE = "module"
    KNOWLEDGE_POINT = "knowledge_point"


class TaxonomyChangeAction(StrEnum):
    CREATE_MODULE = "create_module"
    UPDATE_MODULE = "update_module"
    CREATE_KNOWLEDGE_POINT = "create_knowledge_point"
    UPDATE_KNOWLEDGE_POINT = "update_knowledge_point"
    DEACTIVATE_MODULE = "deactivate_module"
    DEACTIVATE_KNOWLEDGE_POINT = "deactivate_knowledge_point"


class TaxonomyChangeRequest(BaseModel):
    """One explicit taxonomy mutation proposal suitable for previewing."""

    model_config = ConfigDict(extra="forbid")

    action: TaxonomyChangeAction
    code: TaxonomyCode
    name: TaxonomyText | None = None
    description: TaxonomyText | None = None
    course_type: Literal["required", "selective_required"] | None = None
    module_code: TaxonomyCode | None = None
    parent_code: TaxonomyCode | None = None
    clear_parent: bool = False
    sort_order: int | None = Field(default=None, ge=1, le=10_000)
    reason: TaxonomyText | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> "TaxonomyChangeRequest":
        is_module = self.action in {
            TaxonomyChangeAction.CREATE_MODULE,
            TaxonomyChangeAction.UPDATE_MODULE,
            TaxonomyChangeAction.DEACTIVATE_MODULE,
        }
        is_create = self.action in {
            TaxonomyChangeAction.CREATE_MODULE,
            TaxonomyChangeAction.CREATE_KNOWLEDGE_POINT,
        }
        is_update = self.action in {
            TaxonomyChangeAction.UPDATE_MODULE,
            TaxonomyChangeAction.UPDATE_KNOWLEDGE_POINT,
        }
        is_deactivate = self.action in {
            TaxonomyChangeAction.DEACTIVATE_MODULE,
            TaxonomyChangeAction.DEACTIVATE_KNOWLEDGE_POINT,
        }

        if is_create and (self.name is None or self.description is None):
            raise ValueError("create actions require name and description")
        if self.action == TaxonomyChangeAction.CREATE_MODULE and self.course_type is None:
            raise ValueError("create_module requires course_type")
        if (
            self.action == TaxonomyChangeAction.CREATE_KNOWLEDGE_POINT
            and self.module_code is None
        ):
            raise ValueError("create_knowledge_point requires module_code")
        if is_module and (
            self.module_code is not None
            or self.parent_code is not None
            or self.clear_parent
        ):
            raise ValueError("module actions cannot set module_code or parent fields")
        if not is_module and self.course_type is not None:
            raise ValueError("knowledge point actions cannot set course_type")
        if self.parent_code == self.code:
            raise ValueError("a knowledge point cannot be its own parent")
        if self.parent_code is not None and self.clear_parent:
            raise ValueError("parent_code and clear_parent cannot be used together")
        if is_update:
            mutable_values = (
                self.name,
                self.description,
                self.course_type,
                self.module_code,
                self.parent_code,
                self.sort_order,
            )
            if not any(value is not None for value in mutable_values) and not self.clear_parent:
                raise ValueError("update actions require at least one changed field")
        if is_deactivate and any(
            value is not None
            for value in (
                self.name,
                self.description,
                self.course_type,
                self.module_code,
                self.parent_code,
                self.sort_order,
            )
        ):
            raise ValueError("deactivate actions only accept code and reason")
        if is_deactivate and self.clear_parent:
            raise ValueError("deactivate actions cannot clear parent")
        return self

    @property
    def entity_type(self) -> TaxonomyEntityType:
        if self.action in {
            TaxonomyChangeAction.CREATE_MODULE,
            TaxonomyChangeAction.UPDATE_MODULE,
            TaxonomyChangeAction.DEACTIVATE_MODULE,
        }:
            return TaxonomyEntityType.MODULE
        return TaxonomyEntityType.KNOWLEDGE_POINT


class TaxonomyItemSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: TaxonomyEntityType
    code: TaxonomyCode
    name: str
    description: str
    sort_order: int = Field(ge=1)
    is_active: bool
    course_type: Literal["required", "selective_required"] | None = None
    module_code: TaxonomyCode | None = None
    parent_code: TaxonomyCode | None = None


class TaxonomyChangePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: TaxonomyChangeAction
    valid: bool
    before: TaxonomyItemSnapshot | None = None
    after: TaxonomyItemSnapshot | None = None
    notices: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class PreviewTaxonomyChangeToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change: TaxonomyChangeRequest


class ApplyTaxonomyChangeToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change: TaxonomyChangeRequest

    @model_validator(mode="after")
    def reject_deactivation(self) -> "ApplyTaxonomyChangeToolInput":
        if self.change.action in {
            TaxonomyChangeAction.DEACTIVATE_MODULE,
            TaxonomyChangeAction.DEACTIVATE_KNOWLEDGE_POINT,
        }:
            raise ValueError("use deactivate_taxonomy_item for deactivation")
        return self


class DeactivateTaxonomyItemToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: TaxonomyEntityType
    code: TaxonomyCode
    reason: TaxonomyText

    def to_change(self) -> TaxonomyChangeRequest:
        return TaxonomyChangeRequest(
            action=(
                TaxonomyChangeAction.DEACTIVATE_MODULE
                if self.entity_type == TaxonomyEntityType.MODULE
                else TaxonomyChangeAction.DEACTIVATE_KNOWLEDGE_POINT
            ),
            code=self.code,
            reason=self.reason,
        )


class TaxonomyChangeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: TaxonomyChangeAction
    applied: bool
    before: TaxonomyItemSnapshot | None = None
    item: TaxonomyItemSnapshot
    notices: list[str] = Field(default_factory=list)
    message: str

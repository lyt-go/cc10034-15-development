"""通用接口契约；模块字段由领域服务持有，不再为每个模块复制一份模型类。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ActionPayload(BaseModel):
    action: str
    remark: str | None = None


class ClosureSubmitPayload(BaseModel):
    """整改人提交销项。"""
    issue_id: int
    rectify_note: str


class ReviewDecisionPayload(BaseModel):
    """发布人复核销项单。"""
    approve: bool
    reviewer: str
    recheck_note: str
    opinion: str | None = None


class NewRiskPayload(BaseModel):
    """同资源新风险登记（旧销项单不能盖掉新发现）。"""
    resource: str
    problem: str
    level: str | None = "中"
    source_task: str | None = ""
    owner: str | None = ""

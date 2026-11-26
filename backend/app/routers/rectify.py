"""整改复核路由：提交销项、发布人复核、新风险登记与工作流查询。

所有业务判断都在 RectifyReviewService / RiskIssueService 内完成，
路由只负责参数解包和 HTTP 状态映射。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ClosureSubmitPayload, NewRiskPayload, ReviewDecisionPayload
from app.services.rectify import RectifyReviewService, RiskIssueService

router = APIRouter(prefix="/api/rectify", tags=["整改复核"])

rectify_service = RectifyReviewService()
issue_service = RiskIssueService()


@router.get("/issues")
def list_issues(
    resource: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
) -> dict[str, Any]:
    items = issue_service.list_issues(resource=resource, status=status, keyword=keyword)
    return {"items": items, "total": len(items)}


@router.get("/issues/{issue_id}")
def get_issue(issue_id: int) -> dict[str, Any]:
    issue = issue_service.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail=f"风险问题 {issue_id} 不存在或已归档")
    return issue


@router.get("/reviews")
def list_reviews(status: str | None = Query(default=None)) -> dict[str, Any]:
    items = rectify_service.list_reviews(status=status)
    return {"items": items, "total": len(items)}


@router.get("/reviews/{review_id}")
def get_review(review_id: int) -> dict[str, Any]:
    review = rectify_service.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"整改销项单 {review_id} 不存在或已归档")
    return review


@router.post("/closures")
def submit_closure(payload: ClosureSubmitPayload) -> dict[str, Any]:
    data, message = rectify_service.submit_closure(payload.issue_id, payload.rectify_note)
    if data is None:
        return {"ok": False, "message": message}
    return {"ok": True, "message": message, **data}


@router.post("/reviews/{review_id}/decision")
def decide_review(review_id: int, payload: ReviewDecisionPayload) -> dict[str, Any]:
    data, message = rectify_service.decide_review(
        review_id,
        approve=payload.approve,
        reviewer=payload.reviewer,
        recheck_note=payload.recheck_note,
        opinion=payload.opinion or "",
    )
    if data is None:
        return {"ok": False, "message": message}
    return {"ok": True, "message": message, **data}


@router.post("/new-risk")
def register_new_risk(payload: NewRiskPayload) -> dict[str, Any]:
    issue, message = rectify_service.register_new_risk(
        resource=payload.resource,
        problem=payload.problem,
        level=payload.level or "中",
        source_task=payload.source_task or "",
        owner=payload.owner or "",
    )
    if issue is None:
        return {"ok": False, "message": message}
    return {"ok": True, "message": message, "entry": issue}

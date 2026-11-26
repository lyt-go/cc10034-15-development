"""策略发布资格路由：策略下发详情页据此判断关联资源是否重新具备发布资格。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services import service_for

router = APIRouter(prefix="/api/deploy-policies", tags=["策略发布资格"])


@router.get("/{policy_id}/eligibility")
def policy_eligibility(policy_id: int) -> dict:
    service = service_for("deploy_policy")
    verdict, message = service.publish_eligibility(policy_id)
    if verdict is None:
        raise HTTPException(status_code=404, detail=message)
    verdict["message"] = message
    return verdict

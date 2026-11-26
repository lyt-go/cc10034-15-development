"""业务路由汇总：专项路由必须先于通用资源路由注册，否则固定路径会被动态路径抢占。"""
from __future__ import annotations

from app.routers import cross_links, deploy_eligibility, rectify, resource

ROUTERS = [cross_links, rectify, deploy_eligibility, resource]

"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。

下发策略前必须通过整改销项单校验发布资格：只要关联资源上仍有打开的风险问题，
「下发策略」动作会被服务端拦截，并在返回信息中列出阻塞项。
"""
from __future__ import annotations

from app.services.base import BaseModuleService
from app.services.rectify import RectifyReviewService, _split_resources


class DeployPolicyService(BaseModuleService):
    MODULE = "deploy_policy"
    ENTITY = "策略分发"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["分发编号", "策略内容", "目标节点", "关联资源", "下发状态", "生效时间", "冲突策略", "回滚版本", "操作时间"]
    REQUIRED_FIELDS = ["分发编号", "策略内容", "目标节点"]
    STATUS_ORDER = ["待下发", "已生效", "冲突待处理", "已回滚"]
    ACTION_RULES = {"下发策略": "已生效", "标记冲突": "冲突待处理", "回滚策略": "已回滚"}
    NEGATIVE_ACTIONS = ["回滚策略"]

    def __init__(self) -> None:
        self._rectify = RectifyReviewService()

    def run_action(self, entry_id: int, action: str):
        if action == "下发策略":
            policy = self.get_entry(entry_id)
            if policy is not None:
                verdict, _ = self._rectify.evaluate_policy(entry_id)
                if verdict is not None and not verdict["eligible"]:
                    blocked = []
                    for item in verdict["resources"]:
                        if not item["eligible"]:
                            codes = "、".join(
                                f"{b['问题编号']}({b['问题描述']})" for b in item["blockers"]
                            )
                            blocked.append(f"资源 {item['resource']}：{codes}")
                    return None, (
                        "下发被阻塞，关联资源存在未销项风险，先到整改复核页完成销项；"
                        + "；".join(blocked)
                    )
        return super().run_action(entry_id, action)

    def publish_eligibility(self, entry_id: int) -> tuple[dict | None, str]:
        """供详情页发起的发布资格请求：返回逐资源获准情况、阻塞项与历史依据。"""
        return self._rectify.evaluate_policy(entry_id)

    def linked_resources(self, entry_id: int) -> list[str]:
        policy = self.get_entry(entry_id)
        if policy is None:
            return []
        return _split_resources(policy.get("关联资源"))

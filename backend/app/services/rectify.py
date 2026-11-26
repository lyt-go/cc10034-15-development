"""整改复核领域服务。

补齐风险扫描缺失的整改闭环：
  风险问题(risk_issue) —— 整改人提交销项 —— 发布人复核 —— 签发整改销项单(rectify_review)。

关键不变量（全部由服务端校验，路由层不做业务判断）：
1. 复查必须针对待销项的同一资源标识、同一问题描述；资源/问题不一致一律拒绝销项。
2. 旧问题关闭不会盖掉同资源同问题的新发现：新风险另开问题，并回链历史销项单作为依据。
3. 策略下发资格只看当前仍打开的风险；已关闭项通过已签发销项单保留历史依据。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

# 风险问题仍需处理的状态：处于这些状态的问题会阻塞对应资源重新发布。
ISSUE_OPEN_STATUSES = ("待销项", "待复核", "复核驳回")
ISSUE_CLOSED_STATUS = "已关闭"

ISSUE_FIELDS = [
    "问题编号", "关联任务", "资源标识", "问题描述", "风险等级", "发现时间",
    "整改责任人", "整改说明", "提交时间", "销项单号", "关联历史销项单",
]
REVIEW_FIELDS = [
    "销项单号", "问题编号", "资源标识", "问题描述", "来源扫描任务", "整改责任人",
    "整改说明", "提交时间", "复核人", "复查记录", "复核意见", "签发时间", "校验依据",
]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _same(left: Any, right: Any) -> bool:
    return str(left or "").strip().casefold() == str(right or "").strip().casefold()


def _split_resources(raw: Any) -> list[str]:
    return [part.strip() for part in str(raw or "").replace("，", ",").split(",") if part.strip()]


class RiskIssueService:
    """风险问题查询服务：问题本身的状态只允许由整改复核流程改写。"""

    MODULE = "risk_issue"
    ENTITY = "风险问题"
    LIST_FIELDS = ISSUE_FIELDS

    def list_issues(
        self,
        *,
        resource: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = list(store.rows(self.MODULE))
        if resource:
            rows = [row for row in rows if _same(row.get("资源标识"), resource)]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if keyword:
            needle = keyword.strip().casefold()
            rows = [
                row for row in rows
                if needle in str(row.get("问题编号", "")).casefold()
                or needle in str(row.get("问题描述", "")).casefold()
                or needle in str(row.get("资源标识", "")).casefold()
            ]
        return rows

    def get_issue(self, issue_id: int) -> dict[str, Any] | None:
        return store.find(self.MODULE, issue_id)

    def find_by_code(self, issue_code: str) -> dict[str, Any] | None:
        for row in store.rows(self.MODULE):
            if _same(row.get("问题编号"), issue_code):
                return row
        return None

    def open_issues(self, resource: str) -> list[dict[str, Any]]:
        """该资源当前仍打开、会阻塞发布的风险问题。"""
        return [
            row for row in store.rows(self.MODULE)
            if row.get("status") in ISSUE_OPEN_STATUSES and _same(row.get("资源标识"), resource)
        ]

    def closed_history(self, resource: str) -> list[dict[str, Any]]:
        """该资源已关闭问题的历史依据：只取已签发销项单对应的关闭项。"""
        signed = {
            row.get("销项单号")
            for row in store.rows("rectify_review")
            if row.get("status") == "已签发" and _same(row.get("资源标识"), resource)
        }
        return [
            row for row in store.rows(self.MODULE)
            if row.get("status") == ISSUE_CLOSED_STATUS
            and _same(row.get("资源标识"), resource)
            and row.get("销项单号") in signed
        ]


class RectifyReviewService:
    """整改销项单服务：承载提交销项、复核签发、驳回与新风险登记的完整流程。"""

    MODULE = "rectify_review"
    ENTITY = "整改销项单"
    LIST_FIELDS = REVIEW_FIELDS

    def __init__(self) -> None:
        self.issues = RiskIssueService()

    # ———————————————— 查询 ————————————————

    def list_reviews(self, *, status: str | None = None) -> list[dict[str, Any]]:
        rows = list(store.rows(self.MODULE))
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def get_review(self, review_id: int) -> dict[str, Any] | None:
        return store.find(self.MODULE, review_id)

    # ———————————————— 流程动作 ————————————————

    def submit_closure(
        self, issue_id: int, rectify_note: str
    ) -> tuple[dict[str, Any] | None, str]:
        """整改人针对某个风险问题提交销项，生成待复核销项单。"""
        issue = store.find("risk_issue", issue_id)
        if issue is None:
            return None, f"风险问题 {issue_id} 不存在或已归档"
        if issue.get("status") not in ("待销项", "复核驳回"):
            return None, (
                f"问题 {issue.get('问题编号')} 当前状态为「{issue.get('status')}」，"
                "仅待销项或复核驳回的问题可以提交销项"
            )
        note = str(rectify_note or "").strip()
        if not note:
            return None, "提交销项必须填写整改说明，作为发布人复查的依据"

        review_id = store.next_id(self.MODULE)
        cert_no = f"CLR-{review_id:04d}"
        submitted_at = _now()
        review = {
            "id": review_id,
            "status": "待复核",
            "pending": True,
            "abnormal": True,
            "销项单号": cert_no,
            "问题编号": issue.get("问题编号"),
            "资源标识": issue.get("资源标识"),
            "问题描述": issue.get("问题描述"),
            "来源扫描任务": issue.get("关联任务"),
            "整改责任人": issue.get("整改责任人"),
            "整改说明": note,
            "提交时间": submitted_at,
            "复核人": "",
            "复查记录": "",
            "复核意见": "",
            "签发时间": "",
            "校验依据": "",
        }
        store.rows(self.MODULE).append(review)
        issue.update({
            "status": "待复核",
            "pending": True,
            "abnormal": True,
            "整改说明": note,
            "提交时间": submitted_at,
            "销项单号": cert_no,
        })
        return {"issue": issue, "review": review}, f"销项申请已提交（单号 {cert_no}），等待发布人复核"

    def decide_review(
        self,
        review_id: int,
        *,
        approve: bool,
        reviewer: str,
        recheck_note: str,
        opinion: str = "",
    ) -> tuple[dict[str, Any] | None, str]:
        """发布人复核：服务端校验原风险与复查记录后，签发或驳回销项单。"""
        review = store.find(self.MODULE, review_id)
        if review is None:
            return None, f"整改销项单 {review_id} 不存在或已归档"
        if review.get("status") != "待复核":
            return None, f"销项单 {review.get('销项单号')} 已复核（{review.get('status')}），不能重复复核"
        reviewer_name = str(reviewer or "").strip()
        if not reviewer_name:
            return None, "复核必须登记复核人（发布人）"
        recheck = str(recheck_note or "").strip()
        if not recheck:
            return None, "复核必须填写复查记录，服务端需据此校验原风险是否真正整改"

        issue = self.issues.find_by_code(str(review.get("问题编号", "")))
        if issue is None:
            return None, "原风险问题不存在，无法校验复查记录，禁止销项"
        # 核心不变量：复查必须针对待销项的同一资源和同一问题。
        if not _same(issue.get("资源标识"), review.get("资源标识")) or not _same(
            issue.get("问题描述"), review.get("问题描述")
        ):
            return None, (
                "复查记录与原风险的资源或问题不一致，禁止销项："
                "复查必须针对待销项的同一资源和同一问题"
            )

        resource = str(review.get("资源标识", "")).strip()
        problem = str(review.get("问题描述", "")).strip()
        decided_at = _now()
        review.update({
            "复核人": reviewer_name,
            "复查记录": recheck,
            "复核意见": str(opinion or "").strip() or ("复查通过，同意销项" if approve else "复查不通过，驳回整改"),
        })

        if approve:
            review.update({
                "status": "已签发",
                "pending": False,
                "abnormal": False,
                "签发时间": decided_at,
                "校验依据": (
                    f"服务端校验：原风险{issue.get('问题编号')}与复查记录指向同一资源"
                    f"{resource}、同一问题「{problem}」，复查通过，准予销项"
                ),
            })
            issue.update({
                "status": ISSUE_CLOSED_STATUS,
                "pending": False,
                "abnormal": False,
                "销项单号": review.get("销项单号"),
            })
            # 旧问题关闭不能盖掉新发现：同资源同问题若已有新的打开风险，资格仍被阻塞。
            conflicts = [
                row for row in self.issues.open_issues(resource)
                if row.get("id") != issue.get("id") and _same(row.get("问题描述"), problem)
            ]
            if conflicts:
                codes = "、".join(str(row.get("问题编号")) for row in conflicts)
                message = (
                    f"销项单 {review.get('销项单号')} 已签发；但同资源同问题存在新的待处理风险"
                    f"{codes}，该资源仍不具备发布资格"
                )
            else:
                message = f"销项单 {review.get('销项单号')} 已签发，资源 {resource} 对应问题准予销项"
            return {"issue": issue, "review": review, "conflicts": conflicts}, message

        review.update({
            "status": "已驳回",
            "pending": False,
            "abnormal": True,
            "校验依据": (
                f"服务端校验：复查记录针对资源{resource}、问题「{problem}」，复查不通过，驳回整改"
            ),
        })
        issue.update({"status": "复核驳回", "pending": True, "abnormal": True})
        return (
            {"issue": issue, "review": review, "conflicts": []},
            f"销项单 {review.get('销项单号')} 已驳回，整改人可补充材料后重新提交销项",
        )

    def register_new_risk(
        self,
        *,
        resource: str,
        problem: str,
        level: str = "中",
        source_task: str = "",
        owner: str = "",
    ) -> tuple[dict[str, Any] | None, str]:
        """登记同资源（可同问题）的新风险；历史销项单只作依据，不能盖掉新发现。"""
        resource = str(resource or "").strip()
        problem = str(problem or "").strip()
        if not resource or not problem:
            return None, "登记新风险必须填写资源标识和问题描述"
        issue_id = store.next_id("risk_issue")
        prior_certs = [
            str(row.get("销项单号"))
            for row in store.rows(self.MODULE)
            if row.get("status") == "已签发"
            and _same(row.get("资源标识"), resource)
            and _same(row.get("问题描述"), problem)
        ]
        issue = {
            "id": issue_id,
            "status": "待销项",
            "pending": True,
            "abnormal": True,
            "问题编号": f"RI-{issue_id:04d}",
            "关联任务": str(source_task or "").strip() or "人工登记",
            "资源标识": resource,
            "问题描述": problem,
            "风险等级": str(level or "中").strip() or "中",
            "发现时间": _now(),
            "整改责任人": str(owner or "").strip() or "待分派",
            "整改说明": "",
            "提交时间": "",
            "销项单号": "",
            "关联历史销项单": ",".join(prior_certs),
        }
        store.rows("risk_issue").append(issue)
        if prior_certs:
            message = (
                f"新风险 {issue['问题编号']} 已登记；历史销项单 {','.join(prior_certs)} "
                "仅作整改依据，不能盖掉本次新发现，资源发布资格重新被阻塞"
            )
        else:
            message = f"新风险 {issue['问题编号']} 已登记，资源 {resource} 发布资格被阻塞"
        return issue, message

    # ———————————————— 发布资格 ————————————————

    def resource_eligibility(self, resource: str) -> dict[str, Any]:
        """单资源发布资格：阻塞项取当前打开风险，历史依据取已签发销项单。"""
        blockers = self.issues.open_issues(resource)
        history = self.issues.closed_history(resource)
        return {
            "resource": resource,
            "eligible": not blockers,
            "blockers": [
                {
                    "问题编号": row.get("问题编号"),
                    "问题描述": row.get("问题描述"),
                    "风险等级": row.get("风险等级"),
                    "status": row.get("status"),
                }
                for row in blockers
            ],
            "closed_history": [
                {
                    "问题编号": row.get("问题编号"),
                    "问题描述": row.get("问题描述"),
                    "销项单号": row.get("销项单号"),
                }
                for row in history
            ],
        }

    def evaluate_policy(self, policy_id: int) -> tuple[dict[str, Any] | None, str]:
        """按策略分发单关联的资源，逐个判定是否重新具备发布资格。"""
        policy = store.find("deploy_policy", policy_id)
        if policy is None:
            return None, f"策略分发 {policy_id} 不存在或已归档"
        resources = _split_resources(policy.get("关联资源"))
        details = [self.resource_eligibility(resource) for resource in resources]
        eligible = all(item["eligible"] for item in details) if details else True
        blocking = [
            f"{item['resource']} 被 {len(item['blockers'])} 项打开风险阻塞"
            for item in details if not item["eligible"]
        ]
        message = "关联资源全部具备发布资格" if eligible else "；".join(blocking)
        return {
            "policy_id": policy_id,
            "分发编号": policy.get("分发编号"),
            "策略内容": policy.get("策略内容"),
            "eligible": eligible,
            "resources": details,
            "blocking_summary": blocking,
        }, message

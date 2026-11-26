"""整改复核工作流测试：提交销项 -> 发布人复核 -> 销项单签发 -> 策略发布资格。

覆盖验收场景：同一资源两个风险，一项整改通过、另一项保持打开，
再交错提交销项与同资源新风险，核对策略可下发范围和已关闭项的历史依据。
"""
from __future__ import annotations

from app.services import DeployPolicyService
from app.services.rectify import (
    ISSUE_OPEN_STATUSES,
    RectifyReviewService,
    RiskIssueService,
)


def _issue_codes(rows):
    return [row["问题编号"] for row in rows]


class TestSubmitClosure:
    """整改人提交销项。"""

    def test_submit_creates_pending_review(self):
        svc = RectifyReviewService()
        data, message = svc.submit_closure(1, "已对手机号字段接入格式保留加密，回归扫描未再检出明文")
        assert data is not None, message
        issue, review = data["issue"], data["review"]
        assert issue["status"] == "待复核"
        assert issue["销项单号"] == review["销项单号"]
        assert review["status"] == "待复核"
        assert review["资源标识"] == "orders_db"
        assert review["问题描述"] == issue["问题描述"]
        assert "等待发布人复核" in message

    def test_submit_requires_rectify_note(self):
        svc = RectifyReviewService()
        data, message = svc.submit_closure(2, "   ")
        assert data is None
        assert "整改说明" in message

    def test_submit_unknown_issue_rejected(self):
        svc = RectifyReviewService()
        data, message = svc.submit_closure(99999, "整改完成")
        assert data is None
        assert "不存在" in message

    def test_submit_twice_is_rejected_while_pending(self):
        svc = RectifyReviewService()
        svc.submit_closure(2, "补充审计埋点并回归验证")
        data, message = svc.submit_closure(2, "再次提交")
        assert data is None
        assert "仅待销项或复核驳回" in message


class TestReviewDecision:
    """发布人复核与服务端校验。"""

    def _fresh_review(self, issue_id: int, note: str):
        svc = RectifyReviewService()
        data, _ = svc.submit_closure(issue_id, note)
        return svc, data["review"]

    def test_approve_signs_certificate_and_closes_issue(self):
        svc, review = self._fresh_review(1, "手机号字段已加密存储")
        review_id = review["id"]
        data, message = svc.decide_review(
            review_id,
            approve=True,
            reviewer="发布人-冯安全",
            recheck_note="抽样复查200条记录，手机号均为密文，明文风险消除",
        )
        assert data is not None, message
        assert data["review"]["status"] == "已签发"
        assert data["review"]["签发时间"]
        assert "同一资源" in data["review"]["校验依据"]
        assert data["issue"]["status"] == "已关闭"
        assert data["issue"]["pending"] is False
        assert "已签发" in message

    def test_reject_returns_issue_to_rectifier(self):
        svc, review = self._fresh_review(2, "已加审计日志")
        data, message = svc.decide_review(
            review["id"],
            approve=False,
            reviewer="发布人-冯安全",
            recheck_note="复查发现导出接口仍有3条无审计记录，整改不彻底",
        )
        assert data is not None, message
        assert data["review"]["status"] == "已驳回"
        assert data["issue"]["status"] == "复核驳回"
        assert data["issue"] in svc.issues.open_issues("orders_db")
        # 驳回后允许整改人重新提交
        again, again_msg = svc.submit_closure(data["issue"]["id"], "补齐缺失埋点后二次回归通过")
        assert again is not None, again_msg
        assert again["review"]["status"] == "待复核"

    def test_review_requires_reviewer_and_recheck_note(self):
        svc, review = self._fresh_review(1, "已整改")
        data, message = svc.decide_review(
            review["id"], approve=True, reviewer="", recheck_note="复查通过"
        )
        assert data is None and "复核人" in message
        data, message = svc.decide_review(
            review["id"], approve=True, reviewer="发布人-冯安全", recheck_note=""
        )
        assert data is None and "复查记录" in message

    def test_duplicate_decision_rejected(self):
        svc, review = self._fresh_review(1, "已整改")
        svc.decide_review(
            review["id"], approve=True, reviewer="发布人-冯安全", recheck_note="复查通过"
        )
        data, message = svc.decide_review(
            review["id"], approve=True, reviewer="发布人-冯安全", recheck_note="再次复查"
        )
        assert data is None
        assert "不能重复复核" in message

    def test_same_resource_and_problem_invariant_enforced(self):
        """复查记录与原风险资源/问题不一致时禁止销项（服务端不变量）。"""
        svc, review = self._fresh_review(1, "已整改")
        # 模拟数据被篡改：销项单指向的资源与原风险脱钩
        review["资源标识"] = "totally_other_db"
        data, message = svc.decide_review(
            review["id"], approve=True, reviewer="发布人-冯安全", recheck_note="复查通过"
        )
        assert data is None
        assert "同一资源和同一问题" in message

    def test_seed_signed_certificate_keeps_history_basis(self):
        """种子数据中已签发的 CLR-0001 是 profile_db 已关闭项的历史依据。"""
        issues = RiskIssueService()
        history = issues.closed_history("profile_db")
        assert any(row["销项单号"] == "CLR-0001" for row in history)
        assert issues.open_issues("profile_db") == []


class TestNewRiskDoesNotGetCovered:
    """旧问题关闭不能盖掉同资源同问题的新发现。"""

    def test_recurrent_risk_links_prior_certificate_and_blocks_again(self):
        svc = RectifyReviewService()
        # 先把 RI-0001 整改通过
        data, _ = svc.submit_closure(1, "手机号加密整改完成")
        svc.decide_review(
            data["review"]["id"],
            approve=True,
            reviewer="发布人-冯安全",
            recheck_note="复查密文存储生效",
        )
        assert svc.issues.open_issues("orders_db")  # RI-0002 仍打开
        # 同资源同问题再次发现新风险
        issue, message = svc.register_new_risk(
            resource="orders_db",
            problem="明文存储手机号（PII-01）",
            level="高",
            source_task="RISK-0009",
            owner="周整改",
        )
        assert issue is not None
        assert issue["status"] in ISSUE_OPEN_STATUSES
        assert issue["关联历史销项单"], "新风险必须回链历史销项单"
        assert "不能盖掉" in message
        # 历史关闭项仍在，新风险同时成为阻塞项
        eligibility = svc.resource_eligibility("orders_db")
        blocker_codes = [b["问题编号"] for b in eligibility["blockers"]]
        assert issue["问题编号"] in blocker_codes
        closed_codes = [item["问题编号"] for item in eligibility["closed_history"]]
        assert "RI-0001" in closed_codes

    def test_new_risk_requires_resource_and_problem(self):
        svc = RectifyReviewService()
        issue, message = svc.register_new_risk(resource="", problem="x")
        assert issue is None and "资源标识" in message


class TestPolicyEligibility:
    """策略下发详情页的发布资格判定与动作拦截。"""

    def test_policy_with_open_risk_is_blocked_and_lists_basis(self):
        svc = RectifyReviewService()
        # RI-0001 整改通过、RI-0002 保持打开
        data, _ = svc.submit_closure(1, "手机号加密整改完成")
        svc.decide_review(
            data["review"]["id"],
            approve=True,
            reviewer="发布人-冯安全",
            recheck_note="复查通过",
        )
        verdict, message = svc.evaluate_policy(4)  # DEPL-0004 -> orders_db
        assert verdict is not None
        assert verdict["eligible"] is False
        resource_detail = verdict["resources"][0]
        assert resource_detail["resource"] == "orders_db"
        blocker_codes = [item["问题编号"] for item in resource_detail["blockers"]]
        assert "RI-0002" in blocker_codes
        assert "RI-0001" not in blocker_codes, "已关闭项不得再作为阻塞项"
        history_codes = [item["问题编号"] for item in resource_detail["closed_history"]]
        assert "RI-0001" in history_codes, "已关闭项必须保留历史依据（销项单号可追溯）"
        assert "阻塞" in message

    def test_deploy_action_blocked_server_side(self):
        policy = DeployPolicyService()
        entry, message = policy.run_action(4, "下发策略")
        assert entry is None
        assert "下发被阻塞" in message
        assert "RI-0002" in message
        # 策略状态不得被改写
        assert policy.get_entry(4)["status"] == "待下发"

    def test_clean_resource_is_eligible(self):
        svc = RectifyReviewService()
        detail = svc.resource_eligibility("profile_db")
        assert detail["eligible"] is True
        assert detail["blockers"] == []
        assert any(item["销项单号"] == "CLR-0001" for item in detail["closed_history"])

    def test_multi_resource_policy_partial_block(self):
        svc = RectifyReviewService()
        # DEPL-0001 关联 profile_db、api_gateway_cluster，初始均无打开风险
        verdict, _ = svc.evaluate_policy(1)
        assert verdict["eligible"] is True
        # 其中一个资源冒出新风险，整张单被阻塞，页面能看到具体阻塞资源
        svc.register_new_risk(
            resource="api_gateway_cluster",
            problem="鉴权令牌未过期失效（AUTH-03）",
            level="高",
        )
        verdict, message = svc.evaluate_policy(1)
        assert verdict["eligible"] is False
        assert any("api_gateway_cluster" in item for item in verdict["blocking_summary"])
        assert "阻塞" in message

    def test_close_last_blocker_restores_eligibility(self):
        svc = RectifyReviewService()
        # orders_db 初始有 RI-0001、RI-0002 两个打开风险，先关掉前者
        data1, _ = svc.submit_closure(1, "手机号加密整改完成")
        svc.decide_review(
            data1["review"]["id"],
            approve=True,
            reviewer="发布人-冯安全",
            recheck_note="复查密文存储生效",
        )
        # RI-0002 是 orders_db 上最后一个保持打开的风险
        data, _ = svc.submit_closure(2, "补齐导出审计并回归通过")
        svc.decide_review(
            data["review"]["id"],
            approve=True,
            reviewer="发布人-冯安全",
            recheck_note="复查导出链路审计完整",
        )
        detail = svc.resource_eligibility("orders_db")
        assert detail["eligible"] is True
        # 两张销项单都沉淀为历史依据
        assert {item["销项单号"] for item in detail["closed_history"]} == {
            data1["review"]["销项单号"],
            data["review"]["销项单号"],
        }
        # 资格恢复后服务端放行下发动作
        policy = DeployPolicyService()
        entry, message = policy.run_action(4, "下发策略")
        assert entry is not None, message
        assert entry["status"] == "已生效"


class TestInterleavedScenario:
    """端到端交错场景：两项风险一过一开，交错销项与新风险，全程核对资格。"""

    def test_full_interleaved_flow(self):
        svc = RectifyReviewService()
        issues = RiskIssueService()

        # 1. 两个风险同资源：RI-0001 整改通过，RI-0002 保持打开
        data, _ = svc.submit_closure(1, "手机号明文整改：接入格式保留加密")
        approve_msg = svc.decide_review(
            data["review"]["id"],
            approve=True,
            reviewer="发布人-冯安全",
            recheck_note="抽样200条均为密文",
        )[1]
        assert "已签发" in approve_msg
        assert issues.get_issue(1)["status"] == "已关闭"
        assert issues.get_issue(2)["status"] == "待销项"

        # 2. 对仍打开的 RI-0002 提交销项但复核驳回，资源继续被阻塞
        data2, _ = svc.submit_closure(2, "导出接口加了审计")
        rejected = svc.decide_review(
            data2["review"]["id"],
            approve=False,
            reviewer="发布人-冯安全",
            recheck_note="仍有3条导出无审计，整改不彻底",
        )
        assert rejected[0]["issue"]["status"] == "复核驳回"

        # 3. 交错登记同资源新风险（与已关闭项同问题），旧销项单不能盖掉新发现
        new_issue, new_msg = svc.register_new_risk(
            resource="orders_db",
            problem="明文存储手机号（PII-01）",
            level="高",
            source_task="RISK-0010",
        )
        assert new_issue is not None
        assert new_issue["关联历史销项单"] == data["review"]["销项单号"]

        # 4. 策略页可下发范围：orders_db 仍被阻塞，阻塞项含 RI-0002 与新风险，不含已关闭 RI-0001
        verdict, _ = svc.evaluate_policy(4)
        assert verdict["eligible"] is False
        detail = verdict["resources"][0]
        blockers = {item["问题编号"] for item in detail["blockers"]}
        assert "RI-0002" in blockers
        assert new_issue["问题编号"] in blockers
        assert "RI-0001" not in blockers
        history = {item["问题编号"]: item["销项单号"] for item in detail["closed_history"]}
        assert history.get("RI-0001") == data["review"]["销项单号"]

        # 5. 整改人重新提交 RI-0002 并通过，新风险仍在 -> 依旧不可下发
        again, _ = svc.submit_closure(2, "补齐全部导出审计埋点，二次回归零缺失")
        svc.decide_review(
            again["review"]["id"],
            approve=True,
            reviewer="发布人-冯安全",
            recheck_note="复查导出审计全量覆盖",
        )
        verdict, _ = svc.evaluate_policy(4)
        assert verdict["eligible"] is False
        blockers = {item["问题编号"] for item in verdict["resources"][0]["blockers"]}
        assert blockers == {new_issue["问题编号"]}

        # 6. 新风险走完整改复核后资格恢复，历史依据包含三张销项单
        data3, _ = svc.submit_closure(new_issue["id"], "新检出明文批次已重新加密并加卡口校验")
        svc.decide_review(
            data3["review"]["id"],
            approve=True,
            reviewer="发布人-冯安全",
            recheck_note="复查新批次全部密文且卡口生效",
        )
        detail = svc.resource_eligibility("orders_db")
        assert detail["eligible"] is True
        certs = {item["销项单号"] for item in detail["closed_history"]}
        assert data["review"]["销项单号"] in certs
        assert again["review"]["销项单号"] in certs
        assert data3["review"]["销项单号"] in certs

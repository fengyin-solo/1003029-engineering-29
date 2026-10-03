"""就绪探测的回归测试：推进顺序、断点续探、依赖只装一次、响应结构。"""
from __future__ import annotations

import unittest
from unittest import mock

from app import readiness
from app.readiness import CHECK_ORDER, CheckResult, ReadinessChecker


def ok(name: str) -> CheckResult:
    return CheckResult(name, "ok", "通过")


def failed(name: str) -> CheckResult:
    return CheckResult(name, "failed", "未通过")


class ReportFlowTest(unittest.TestCase):
    def build(self, outcomes: dict[str, list[CheckResult]]):
        """把真实探测换成按剧本返回，只验证编排逻辑。"""
        checker = ReadinessChecker()
        calls: list[str] = []

        def fake_run(name: str) -> CheckResult:
            calls.append(name)
            return outcomes[name].pop(0)

        checker._run = fake_run  # type: ignore[method-assign]
        return checker, calls

    def test_all_ok(self):
        checker, calls = self.build({
            "port": [ok("port")],
            "deps": [ok("deps")],
            "proxy": [ok("proxy")],
        })
        ready, results = checker.report()
        self.assertTrue(ready)
        self.assertEqual([r.status for r in results.values()], ["ok", "ok", "ok"])
        self.assertEqual(calls, ["port", "deps", "proxy"])

    def test_resume_from_failed_item(self):
        checker, calls = self.build({
            "port": [ok("port")],
            "deps": [failed("deps"), ok("deps")],
            "proxy": [ok("proxy")],
        })
        ready, results = checker.report()
        self.assertFalse(ready)
        self.assertEqual(results["deps"].status, "failed")
        self.assertEqual(results["proxy"].status, "pending")

        ready, _ = checker.report()
        self.assertTrue(ready)
        # 第二次探测从没通的 deps 接着来，已通过的 port 没有重跑
        self.assertEqual(calls, ["port", "deps", "deps", "proxy"])

    def test_failed_item_retried_until_ok(self):
        checker, calls = self.build({
            "port": [ok("port")],
            "deps": [ok("deps")],
            "proxy": [failed("proxy"), failed("proxy"), ok("proxy")],
        })
        self.assertFalse(checker.report()[0])
        self.assertFalse(checker.report()[0])
        self.assertTrue(checker.report()[0])
        # 已通过的 port/deps 全程只探了一次，proxy 每次重探
        self.assertEqual(calls, ["port", "deps", "proxy", "proxy", "proxy"])


class DepsRepairTest(unittest.TestCase):
    def test_install_runs_at_most_once(self):
        checker = ReadinessChecker()
        with mock.patch.object(
            readiness, "_missing_distributions", return_value=["pydantic"]
        ), mock.patch.object(readiness, "_install_requirements") as install:
            self.assertEqual(checker._check_deps().status, "failed")
            self.assertEqual(checker._check_deps().status, "failed")
            # 重复探测不会把依赖重复拉起
            self.assertEqual(install.call_count, 1)

    def test_install_rechecks_after_repair(self):
        checker = ReadinessChecker()
        with mock.patch.object(
            readiness, "_missing_distributions", side_effect=[["pydantic"], []]
        ), mock.patch.object(readiness, "_install_requirements") as install:
            result = checker._check_deps()
            self.assertEqual(result.status, "ok")
            self.assertEqual(install.call_count, 1)


class RequirementsParseTest(unittest.TestCase):
    def test_parse_names(self):
        self.assertEqual(
            readiness._required_distributions(), ["fastapi", "uvicorn", "pydantic"]
        )


class ReadyEndpointTest(unittest.TestCase):
    def call_endpoint(self, outcomes: dict[str, list[CheckResult]]):
        from fastapi import Response

        from app import main

        checker = ReadinessChecker()
        checker._run = lambda name: outcomes[name].pop(0)  # type: ignore[method-assign]
        response = Response()
        with mock.patch.object(main, "checker", checker):
            body = main.ready(response)
        return response, body

    def test_not_ready_points_out_failed_item(self):
        response, body = self.call_endpoint({
            "port": [ok("port")],
            "deps": [ok("deps")],
            "proxy": [failed("proxy")],
        })
        self.assertEqual(response.status_code, 503)
        self.assertFalse(body["ready"])
        self.assertEqual(body["retry_from"], "proxy")
        self.assertEqual(set(body["checks"]), set(CHECK_ORDER))
        self.assertEqual(body["checks"]["proxy"]["status"], "failed")

    def test_ready_returns_200(self):
        response, body = self.call_endpoint({
            "port": [ok("port")],
            "deps": [ok("deps")],
            "proxy": [ok("proxy")],
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["ready"])
        self.assertIsNone(body["retry_from"])


if __name__ == "__main__":
    unittest.main()

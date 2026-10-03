"""就绪探测：端口、依赖、代理三项全通才算就绪。

约定：
- 就绪地址固定为 GET /api/ready，任何机器、任何入口看到的都是这一份结论；
- 三项检查按 port -> deps -> proxy 的顺序推进，已通过的项会被记住，
  下次探测从没通的那一项接着来，不会从头重跑；
- 依赖缺失时补装一次（且仅一次），并发或重复探测不会把安装重复拉起；
- 检查只依赖运行配置（app.config.settings）和实际连通性，不依赖某台
  机器的绝对路径，所以同一个就绪地址换一台机器结论口径一致。
"""
from __future__ import annotations

import importlib.metadata
import json
import socket
import subprocess
import sys
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

CHECK_ORDER = ("port", "deps", "proxy")

REQUIREMENTS_FILE = Path(__file__).resolve().parents[1] / "requirements.txt"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # "ok" | "failed" | "pending"
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"status": self.status, "detail": self.detail}


def _ok(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "ok", detail)


def _failed(name: str, detail: str) -> CheckResult:
    return CheckResult(name, "failed", detail)


def _pending(name: str) -> CheckResult:
    return CheckResult(name, "pending", "待探测")


def _required_distributions() -> list[str]:
    """从 requirements.txt 读出应安装的发行包名（去掉 extras 和版本约束）。"""
    names: list[str] = []
    for raw in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("[", 1)[0]  # uvicorn[standard] -> uvicorn
        for sep in (">=", "<=", "==", "~=", "!=", ">", "<"):
            name = name.split(sep, 1)[0]
        name = name.strip()
        if name:
            names.append(name)
    return names


def _missing_distributions() -> list[str]:
    """对照 requirements.txt，列出环境里没装全的包。"""
    missing: list[str] = []
    for name in _required_distributions():
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    return missing


def _install_requirements() -> None:
    """补装依赖。只会被 ReadinessChecker 在"还没装过"的前提下调用一次。"""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS_FILE)],
        check=False,
        timeout=300,
    )


class ReadinessChecker:
    """按固定顺序探测并记住进度：只往前推进，不回头重跑已通过的项。"""

    def __init__(self) -> None:
        # 探测全程串行：既保证断点续探的进度不丢，也保证依赖安装不会被
        # 并发/重复探测重复拉起。
        self._lock = threading.Lock()
        self._passed: dict[str, CheckResult] = {}
        self._deps_repair_attempted = False

    def report(self) -> tuple[bool, dict[str, CheckResult]]:
        """返回 (是否就绪, 各项结果)。没通时结果里标出卡在哪一项。"""
        with self._lock:
            results: dict[str, CheckResult] = {}
            for name in CHECK_ORDER:
                if name in self._passed:
                    results[name] = self._passed[name]
                    continue
                result = self._run(name)
                results[name] = result
                if result.status != "ok":
                    # 卡住的项之后都还没探，标成待探测
                    for rest in CHECK_ORDER:
                        if rest not in results:
                            results[rest] = _pending(rest)
                    break
                self._passed[name] = result
            ready = all(item.status == "ok" for item in results.values())
            return ready, results

    def _run(self, name: str) -> CheckResult:
        if name == "port":
            return self._check_port()
        if name == "deps":
            return self._check_deps()
        return self._check_proxy()

    def _check_port(self) -> CheckResult:
        port = settings.port
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return _ok("port", f"端口 {port} 已在监听")
        except OSError as exc:
            return _failed(
                "port", f"端口 {port} 未监听（APP_PORT={port}，检查启动端口是否对齐）：{exc}"
            )

    def _check_deps(self) -> CheckResult:
        missing = _missing_distributions()
        if missing and not self._deps_repair_attempted:
            # 安装只拉起一次：之后的重复探测直接复用这次的结果
            self._deps_repair_attempted = True
            _install_requirements()
            missing = _missing_distributions()
        if missing:
            return _failed("deps", "依赖未装全：" + "、".join(missing))
        return _ok("deps", f"依赖已装全（{len(_required_distributions())} 项）")

    def _check_proxy(self) -> CheckResult:
        url = settings.proxy_health_url
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # 前端没起、代理没配、指错地方都归到这一项
            return _failed("proxy", f"前端代理不可达（{url}）：{exc}")
        if payload.get("instance") == settings.instance_id:
            return _ok("proxy", f"代理已指向本服务（{url}）")
        return _failed(
            "proxy",
            f"代理经 {url} 指向了另一个后端进程，检查 VITE_PROXY_TARGET / PROXY_HEALTH_URL",
        )


checker = ReadinessChecker()

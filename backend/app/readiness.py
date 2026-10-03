"""就绪探测：端口、依赖、代理三项成一链，没过哪项点哪项，重试从断点续探。

约定：
- 检查顺序固定为 port → deps → proxy，前一项没过，后面的项记为待探测，不白跑。
- 已通过的项在进程内缓存，重试只从未通过的那项接着探；所有检查都是只读的，
  重复探测不会重复装依赖、不会重复拉起任何服务。
- 同一套检查服务多个入口：GET /api/ready、`python -m app.readiness`（make ready）、
  docker-compose 的 healthcheck，结论只由配置（APP_HOST/APP_PORT/APP_PROXY_URL）决定，
  换一台机器、换一个入口，看到的结论一致。

注意：本模块只依赖标准库和 app.config，保证依赖缺失时 CLI 入口也能正常跑出 deps 报告，
而不是自己先 import 失败。
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from app.config import settings

# 与 requirements.txt 对齐的最低版本
REQUIRED_DEPS: dict[str, str] = {
    "fastapi": "0.110",
    "uvicorn": "0.29",
    "pydantic": "2.6",
}

CHECK_ORDER = ("port", "deps", "proxy")

# 前端代理转发时带的标记头（见 frontend/vite.config.ts），
# 用来区分"真的经过了前端代理"和"APP_PROXY_URL 直接指了后端"。
PROXY_HEADER = "x-proxied-by"
PROXY_MARKER = "vite-dev"

_PROBE_TIMEOUT_SECONDS = 2.0


def server_token() -> str:
    """服务身份令牌：同一份配置算出同一个值，换实例/换端口就对不上。

    代理检查靠它确认代理后面站的是本服务；令牌由配置推导，不随进程变化，
    所以 HTTP 入口和 CLI 入口算出来的结论一致。
    """
    raw = f"{settings.app_name}|{settings.env}|{settings.host}|{settings.port}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool | None  # None 表示前项未过、还没轮到探测
    detail: str
    cached: bool = False
    duration_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "cached": self.cached,
            "duration_ms": self.duration_ms,
        }


def _check_port() -> tuple[bool, str]:
    host = "127.0.0.1" if settings.host in ("0.0.0.0", "::") else settings.host
    try:
        with socket.create_connection((host, settings.port), timeout=_PROBE_TIMEOUT_SECONDS):
            return True, f"{settings.host}:{settings.port} 已在监听"
    except OSError as exc:
        return False, f"{settings.host}:{settings.port} 连不上：{exc}"


def _version_tuple(text: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in text.split("."):
        digits = ""
        for ch in piece:
            if not ch.isdigit():
                break
            digits += ch
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _check_deps() -> tuple[bool, str]:
    problems: list[str] = []
    versions: list[str] = []
    for dist, minimum in REQUIRED_DEPS.items():
        try:
            installed = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            problems.append(f"{dist} 未安装")
            continue
        versions.append(f"{dist} {installed}")
        if _version_tuple(installed) < _version_tuple(minimum):
            problems.append(f"{dist} {installed} 低于要求的 {minimum}")
    if problems:
        return False, "；".join(problems) + "（先跑 make install 或 backend/run.sh 装齐）"
    return True, "依赖齐全：" + "、".join(versions)


def _check_proxy() -> tuple[bool, str]:
    url = settings.proxy_url.rstrip("/") + "/api/health"
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=_PROBE_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return False, f"{settings.proxy_url} 返回 {exc.code}（代理目标不是本服务？）"
    except urllib.error.URLError as exc:
        return False, f"{settings.proxy_url} 不可达：{exc.reason}（前端 dev server 没起？）"
    except (ValueError, OSError) as exc:
        return False, f"{settings.proxy_url} 返回无法解析：{exc}"
    if payload.get("app") != settings.app_name or payload.get("instance") != server_token():
        return False, f"{settings.proxy_url} 背后不是本服务实例（代理目标指错了？）"
    if not payload.get("via_proxy"):
        return False, f"{settings.proxy_url} 直达了后端、没经过前端代理（APP_PROXY_URL 指错了？）"
    return True, f"{settings.proxy_url} 的 /api 代理已指回本服务"


_CHECKS: dict[str, Callable[[], tuple[bool, str]]] = {
    "port": _check_port,
    "deps": _check_deps,
    "proxy": _check_proxy,
}


class _Probe:
    """断点续探：通过的项缓存起来，重试只从未通过的项接着跑。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._passed: dict[str, CheckResult] = {}

    def run(self) -> dict[str, Any]:
        # 并发探测同一时刻只跑一轮，已过的项不会被重复拉起
        with self._lock:
            results: list[CheckResult] = []
            blocked = False
            for name in CHECK_ORDER:
                if blocked:
                    results.append(CheckResult(name, None, "等待前置项通过后探测"))
                    continue
                cached = self._passed.get(name)
                if cached is not None:
                    results.append(cached)
                    continue
                started = time.monotonic()
                ok, detail = _CHECKS[name]()
                elapsed_ms = int((time.monotonic() - started) * 1000)
                if ok:
                    self._passed[name] = CheckResult(name, True, detail, cached=True, duration_ms=elapsed_ms)
                    results.append(CheckResult(name, True, detail, duration_ms=elapsed_ms))
                else:
                    results.append(CheckResult(name, False, detail, duration_ms=elapsed_ms))
                    blocked = True
            failed = [item.name for item in results if item.ok is False]
            ready = not failed and all(item.ok for item in results)
            if ready:
                hint = "全部通过"
            else:
                hint = f"修复 {failed[0]} 后重新探测，将从 {failed[0]} 接着探，已通过的项不会重跑"
            return {
                "ready": ready,
                "app": settings.app_name,
                "env": settings.env,
                "instance": server_token(),
                "checks": [item.as_dict() for item in results],
                "failed": failed,
                "hint": hint,
            }


_probe = _Probe()


def run_checks() -> dict[str, Any]:
    """跑一轮就绪探测（带断点续探），返回结构化报告。"""
    return _probe.run()


def main() -> int:
    """CLI 入口：`python -m app.readiness`，与 /api/ready 同一套检查。"""
    report = run_checks()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""通信基站运维管理平台 后端服务入口。

启动：uvicorn app.main:app --host 127.0.0.1 --port 8000
健康检查：GET /api/health（活没活）
就绪检查：GET /api/ready（好没好，端口/依赖/代理全通才回 200）
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import readiness
from app.config import settings
from app.routers import ROUTERS
from app.store import store

app = FastAPI(title="通信基站运维管理平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in ROUTERS:
    app.include_router(module.router)


@app.get("/api/health")
def health(request: Request) -> dict[str, object]:
    """存活检查：确认服务已经监听、示例数据已经就绪。

    via_proxy 给就绪探测的 proxy 项用：请求带着前端代理的标记头才算真经过了代理。
    """
    return {
        "ok": True,
        "app": settings.app_name,
        "instance": readiness.server_token(),
        "via_proxy": request.headers.get(readiness.PROXY_HEADER) == readiness.PROXY_MARKER,
        "modules": len(store.module_names()),
        "ready_url": "/api/ready",
    }


@app.get("/api/ready")
def ready() -> JSONResponse:
    """就绪检查：端口、依赖、代理全通才回 200，缺哪项在 failed 里点出来。

    未就绪回 503，body 里同样带逐项明细；已通过的项进程内缓存，
    重试从未通过的那项接着探，重复调用没有副作用。
    """
    report = readiness.run_checks()
    return JSONResponse(
        status_code=200 if report["ready"] else 503,
        content=report,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/overview")
def overview() -> dict[str, object]:
    """运营概览：把各业务模块的待处理量汇总成看板卡片。"""
    return store.overview()

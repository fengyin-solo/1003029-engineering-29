"""通信基站运维管理平台 后端服务入口。

启动：uvicorn app.main:app --host 127.0.0.1 --port 8000
健康检查：GET /api/health
就绪探测：GET /api/ready（端口、依赖、代理全通才回就绪）
"""
from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.readiness import CHECK_ORDER, checker
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
def health() -> dict[str, object]:
    """健康检查：确认服务已经监听、示例数据已经就绪。

    instance 是本进程的标识，就绪探测用它确认前端代理指向的是这个后端。
    """
    return {
        "ok": True,
        "app": settings.app_name,
        "instance": settings.instance_id,
        "modules": len(store.module_names()),
    }


@app.get("/api/ready")
def ready(response: Response) -> dict[str, object]:
    """就绪探测：端口、依赖、代理三项全通才回 ready=true，否则 503。

    没通时 checks 里点出是哪一项没过，retry_from 指明下次探测从哪项接着来；
    已通过的项不会重跑，依赖也不会被重复安装。
    """
    ok, results = checker.report()
    if not ok:
        response.status_code = 503
    retry_from = next((n for n in CHECK_ORDER if results[n].status != "ok"), None)
    return {
        "ready": ok,
        "instance": settings.instance_id,
        "retry_from": retry_from,
        "checks": {name: result.as_dict() for name, result in results.items()},
    }


@app.get("/api/overview")
def overview() -> dict[str, object]:
    """运营概览：把各业务模块的待处理量汇总成看板卡片。"""
    return store.overview()

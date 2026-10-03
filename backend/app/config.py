"""运行配置：端口、跨域、运行环境。

所有与环境相关的取值都允许用环境变量覆盖，换一台机器部署时不需要改代码，
就绪探测读的也是这份配置，保证任何入口看到的结论一致。
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    app_name: str = "通信基站运维管理平台"
    env: str = field(default_factory=lambda: os.getenv("APP_ENV", "local"))
    # 服务监听端口：run.sh 会把它和 uvicorn 的 --port 对齐
    port: int = field(default_factory=lambda: int(os.getenv("APP_PORT", "8000")))
    # 前端代理回源到本服务的健康地址：就绪探测用它确认"代理指对了没有"。
    # 本地开发是 vite 的 5173；换环境（如 docker 网络）用 PROXY_HEALTH_URL 覆盖。
    proxy_health_url: str = field(
        default_factory=lambda: os.getenv(
            "PROXY_HEALTH_URL", "http://127.0.0.1:5173/api/health"
        )
    )
    # 每个进程一份的实例标识：用来识别代理指向的是不是"这个"后端进程
    instance_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )
    page_size_default: int = 20
    page_size_max: int = 200


settings = Settings()

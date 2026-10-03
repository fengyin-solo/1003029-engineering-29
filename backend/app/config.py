"""运行配置：监听地址、跨域、运行环境、就绪探测目标。

全部支持环境变量覆盖，默认值保持原样，老启动命令（run.sh / make backend）不用改。
换机器部署时只需要对齐这几个变量，就绪地址给出的结论就和本地一致。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _allowed_origins() -> list[str]:
    raw = os.environ.get(
        "APP_ALLOWED_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    )
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "通信基站运维管理平台"
    env: str = os.environ.get("APP_ENV", "local")
    host: str = os.environ.get("APP_HOST", "127.0.0.1")
    port: int = int(os.environ.get("APP_PORT", "8000"))
    # 前端 dev server 地址：就绪探测的 proxy 项会顺着它验证 /api 代理指回本服务
    proxy_url: str = os.environ.get("APP_PROXY_URL", "http://127.0.0.1:5173")
    allowed_origins: list[str] = field(default_factory=_allowed_origins)
    page_size_default: int = 20
    page_size_max: int = 200


settings = Settings()

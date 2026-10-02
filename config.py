"""运行配置：全部通过环境变量注入，代码里不写死地址与密钥。

| 环境变量             | 默认值                  | 说明                                        |
| -------------------- | ----------------------- | ------------------------------------------- |
| CALC_DB_PATH         | ./data/calculator.db    | SQLite 文件路径                             |
| CALC_CORS_ORIGINS    | *                       | 允许的前端来源，多个用英文逗号分隔           |
| CALC_APP_NAME        | 计算器后端 API          | Swagger 标题                                |
| CALC_LOG_LEVEL       | INFO                    | 日志级别                                    |
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Settings:
    """轻量配置对象（避免为一个小项目引入 pydantic-settings）。"""

    def __init__(self) -> None:
        self.app_name: str = os.getenv("CALC_APP_NAME", "计算器后端 API")
        self.version: str = "1.0.0"
        self.log_level: str = os.getenv("CALC_LOG_LEVEL", "INFO").upper()

        db_path = os.getenv("CALC_DB_PATH", "").strip()
        self.db_path: Path = Path(db_path).expanduser() if db_path else BASE_DIR / "data" / "calculator.db"

        raw_origins = os.getenv("CALC_CORS_ORIGINS", "*").strip()
        if raw_origins in ("", "*"):
            # 开发 / 演示环境放开；生产环境请显式配置，例如：
            # CALC_CORS_ORIGINS=https://calculator-frontend-xxx.vercel.app
            self.cors_origins: list[str] = ["*"]
        else:
            self.cors_origins = [o.strip().rstrip("/") for o in raw_origins.split(",") if o.strip()]


settings = Settings()


def configure_logging() -> None:
    """统一日志格式，方便在 Render 日志面板里排查问题。"""
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )

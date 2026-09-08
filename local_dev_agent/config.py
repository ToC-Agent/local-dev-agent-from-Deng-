"""从环境变量读取百炼配置。不打印 Key。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from local_dev_agent.gateway.bailian import DEFAULT_BASE_URL, DEFAULT_MODEL


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str


def load_settings(model_override: str | None = None) -> Settings:
    api_key = (os.environ.get("DASHSCOPE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "未找到 DASHSCOPE_API_KEY。请确认用户级环境变量已设置，并新开一个终端。"
        )
    base_url = (
        os.environ.get("DASHSCOPE_BASE_URL") or DEFAULT_BASE_URL
    ).strip()
    model = (model_override or os.environ.get("DASHSCOPE_MODEL") or DEFAULT_MODEL).strip()
    return Settings(api_key=api_key, base_url=base_url, model=model)

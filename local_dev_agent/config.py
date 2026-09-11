"""读取模型通道配置。不打印 Key。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from local_dev_agent.gateway.bailian import (
    DEFAULT_BASE_URL as BAILIAN_BASE,
    DEFAULT_MODEL as BAILIAN_MODEL,
    BailianProvider,
)
from local_dev_agent.gateway.openai_compat import OpenAICompatProvider
from local_dev_agent.gateway.zhongtai import (
    DEFAULT_BASE_URL as ZHONGTAI_BASE,
    DEFAULT_MODEL as ZHONGTAI_MODEL,
    ZhongtaiProvider,
)


@dataclass(frozen=True)
class Settings:
    provider: str
    api_key: str
    base_url: str
    model: str


def load_settings(
    model_override: str | None = None,
    provider_override: str | None = None,
) -> Settings:
    provider = (
        provider_override or os.environ.get("AGENT_PROVIDER") or "zhongtai"
    ).strip().lower()
    if provider == "zhongtai":
        api_key = (os.environ.get("ZHONGTAI_API_KEY") or "").strip() or _mcp_zhongtai_key()
        if not api_key:
            raise RuntimeError(
                "未找到中台 Key。请设置用户级环境变量 ZHONGTAI_API_KEY，"
                "或在 Cursor 的 mcp.json 里为中台 MCP 配置 X-API-Key。"
            )
        base_url = (os.environ.get("ZHONGTAI_BASE_URL") or ZHONGTAI_BASE).strip()
        model = (model_override or os.environ.get("ZHONGTAI_MODEL") or ZHONGTAI_MODEL).strip()
        return Settings(provider="zhongtai", api_key=api_key, base_url=base_url, model=model)

    if provider == "bailian":
        api_key = (os.environ.get("DASHSCOPE_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("未找到 DASHSCOPE_API_KEY。")
        base_url = (os.environ.get("DASHSCOPE_BASE_URL") or BAILIAN_BASE).strip()
        model = (model_override or os.environ.get("DASHSCOPE_MODEL") or BAILIAN_MODEL).strip()
        return Settings(provider="bailian", api_key=api_key, base_url=base_url, model=model)

    raise RuntimeError(f"未知 provider: {provider}（支持 zhongtai / bailian）")


def build_provider(settings: Settings) -> OpenAICompatProvider:
    if settings.provider == "zhongtai":
        return ZhongtaiProvider(
            api_key=settings.api_key,
            base_url=settings.base_url,
            model=settings.model,
        )
    return BailianProvider(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
    )


def _mcp_zhongtai_key() -> str:
    """本机 Cursor 已配中台 MCP 时，复用同一把 X-API-Key，不入库。"""
    path = Path.home() / ".cursor" / "mcp.json"
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ""
    for spec in (data.get("mcpServers") or {}).values():
        if not isinstance(spec, dict):
            continue
        url = str(spec.get("url") or "")
        headers = spec.get("headers") if isinstance(spec.get("headers"), dict) else {}
        key = str(headers.get("X-API-Key") or headers.get("x-api-key") or "").strip()
        if key and "10.8.144.65" in url:
            return key
    return ""

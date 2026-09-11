"""智能体中台 OpenAI 兼容口（X-API-Key，内网网关）。"""

from __future__ import annotations

from local_dev_agent.gateway.openai_compat import OpenAICompatProvider

DEFAULT_BASE_URL = "http://10.8.144.65:30191/v1"
DEFAULT_MODEL = "qwen3.7-plus"


class ZhongtaiProvider(OpenAICompatProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise ValueError("ZHONGTAI_API_KEY 为空")
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            auth="x-api-key",
            timeout=timeout,
        )

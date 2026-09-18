"""LLM response helpers shared by Anthropic-compatible providers."""
from typing import Any, Iterable, List, Optional
from urllib.parse import urlparse

from anthropic import AsyncAnthropic


def create_async_client(api_key: str, base_url: Optional[str] = None, **options: Any) -> AsyncAnthropic:
    """Use Bearer authentication for SiliconFlow's Anthropic Messages endpoint."""
    kwargs = {"api_key": api_key, "timeout": 60.0, "max_retries": 1, **options}
    if base_url:
        kwargs["base_url"] = base_url
        if urlparse(base_url).hostname in {"api.siliconflow.cn", "api.siliconflow.com"}:
            # SDK 0.40 prioritizes X-Api-Key even when auth_token is set.
            # Explicitly include the provider-required Authorization header.
            kwargs["default_headers"] = {
                **kwargs.get("default_headers", {}),
                "Authorization": f"Bearer {api_key}",
            }
    return AsyncAnthropic(**kwargs)


def extract_text_content(content: Iterable[Any]) -> str:
    """Return text blocks from Anthropic-style response content."""
    texts: List[str] = []
    for block in content or []:
        if isinstance(block, str):
            texts.append(block)
            continue

        block_type = getattr(block, "type", None)
        text = getattr(block, "text", None)
        if isinstance(block, dict):
            block_type = block.get("type", block_type)
            text = block.get("text", text)

        if isinstance(text, str) and (block_type in (None, "text")):
            texts.append(text)

    return "\n".join(t for t in texts if t)

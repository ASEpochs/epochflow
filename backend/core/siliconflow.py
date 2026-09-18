"""Small, bounded remote API client. No model weights or generated files on disk."""
import base64
import os
import time
import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from core.model_catalog import CATALOG


def provider_config():
    base = os.getenv("ANTHROPIC_BASE_URL", "https://api.siliconflow.cn").rstrip("/")
    if base not in {"https://api.siliconflow.cn", "https://api.siliconflow.com",
                    "https://api.siliconflow.cn/v1", "https://api.siliconflow.com/v1"}:
        raise HTTPException(503, "模型中心需要后端配置硅基流动 API 地址")
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key or key in {"your_api_key", "changeme"}:
        raise HTTPException(503, "硅基流动 API 密钥尚未配置")
    return base.removesuffix("/v1") + "/v1", key


async def request(endpoint, payload=None, *, method="POST", binary=False):
    base, key = provider_config()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(150, connect=15)) as client:
            # Streaming read imposes a response cap, including audio, on the free worker.
            async with client.stream(method, f"{base}/{endpoint}", json=payload,
                                     headers={"Authorization": f"Bearer {key}"}) as response:
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 16 * 1024 * 1024:
                        raise HTTPException(502, "模型结果过大，请缩短输入后再试")
                if not response.is_success:
                    messages = {400: "输入或模型参数不被支持", 401: "API 密钥验证失败", 402: "余额不足",
                                403: "账号无权调用此模型", 404: "该模型或接口当前不可用",
                                429: "额度不足或请求过于频繁", 503: "模型服务繁忙"}
                    # Do not echo upstream bodies: they may contain credentials or user media.
                    raise HTTPException(502, f"硅基流动：{messages.get(response.status_code, '请求失败')}（{response.status_code}）。请在平台核对模型权限与额度。")
                if binary:
                    return {"audio": "data:audio/mpeg;base64," + base64.b64encode(data).decode()}
                import json
                try:
                    return json.loads(data)
                except (ValueError, UnicodeDecodeError):
                    raise HTTPException(502, "模型平台返回了无法解析的结果") from None
    except httpx.TimeoutException:
        raise HTTPException(504, "模型平台响应超时；生成任务请先查询状态，避免重复提交") from None
    except httpx.HTTPError:
        raise HTTPException(502, "暂时无法连接硅基流动，请稍后再试") from None


_catalog_lock = asyncio.Lock()
_catalog_cache = None
_catalog_expiry = 0


async def catalog_status():
    global _catalog_cache, _catalog_expiry
    async with _catalog_lock:
        if _catalog_cache is not None and time.monotonic() < _catalog_expiry:
            return _catalog_cache
        try:
            response = await request("models", method="GET")
            ids = {item["id"] for item in response["data"]}
            error = ""
        except (HTTPException, KeyError, TypeError) as ex:
            ids = None
            error = ex.detail if isinstance(ex, HTTPException) else "暂时无法读取平台模型清单"
        items = [{**item, "provider_listed": None if ids is None else item["id"] in ids,
                  "availability": ("requires_adapter" if item["category"] == "lora" else
                  "unknown" if ids is None else "listed" if item["id"] in ids else "not_listed")}
                 for item in CATALOG]
        _catalog_cache = {"items": items, "checked_at": datetime.now(timezone.utc).isoformat(),
                          "error": error, "default_model": os.getenv("ANTHROPIC_MODEL", ""),
                          "listed_count": sum(item["provider_listed"] is True for item in items),
                          "note": "已列出表示账号模型清单中存在，不保证额度、接口能力或代金券抵扣。以平台实际请求和账单为准。"}
        _catalog_expiry = time.monotonic() + (300 if ids is not None else 30)
        return _catalog_cache

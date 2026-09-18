import asyncio
import json

import httpx

from core.llm_utils import create_async_client, extract_text_content


def test_siliconflow_messages_use_bearer_and_preserve_tool_blocks():
    async def run():
        def handle(request):
            assert str(request.url) == "https://api.siliconflow.cn/v1/messages"
            assert request.headers["Authorization"] == "Bearer test-key"
            payload = json.loads(request.content)
            assert payload["tools"][0]["input_schema"]["type"] == "object"
            return httpx.Response(200, json={
                "id": "msg_test", "type": "message", "role": "assistant",
                "model": "test-model", "stop_reason": "tool_use", "stop_sequence": None,
                "content": [{"type": "tool_use", "id": "tool_test", "name": "check", "input": {}}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            })

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        async with create_async_client(
            "test-key", "https://api.siliconflow.cn", http_client=http_client,
        ) as client:
            response = await client.messages.create(
                model="test-model", max_tokens=32,
                messages=[{"role": "user", "content": "check"}],
                tools=[{"name": "check", "input_schema": {"type": "object", "properties": {}}}],
            )
            assert response.content[0].name == "check"
            assert response.content[0].input == {}

    asyncio.run(run())


def test_non_siliconflow_provider_keeps_api_key_auth(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    async def run():
        async with create_async_client("test-key", "https://api.anthropic.com") as client:
            assert client.auth_token is None
            assert client.api_key == "test-key"

    asyncio.run(run())


def test_extract_text_ignores_reasoning_and_tool_blocks():
    assert extract_text_content([
        {"type": "thinking", "thinking": "internal reasoning"},
        {"type": "tool_use", "name": "check", "input": {}},
        {"type": "text", "text": "OK"},
    ]) == "OK"

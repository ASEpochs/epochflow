"""Request-local Agent model selection with OpenAI tool-call translation."""
import json
from contextvars import ContextVar
from contextlib import asynccontextmanager
from types import SimpleNamespace

from anthropic.resources.messages import AsyncMessages
from fastapi import HTTPException
from core import siliconflow
from core.model_catalog import AGENT_MODELS

selected_model = ContextVar("epochflow_model", default=None)
model_errors = ContextVar("epochflow_model_errors", default=None)


@asynccontextmanager
async def agent_model_scope(req):
    if req.model and req.model not in AGENT_MODELS:
        raise HTTPException(400, "此模型请在模型中心体验；Agent 对话仅开放工具调用模型")
    token = selected_model.set(req.model)
    errors = model_errors.set([])
    try:
        yield
    finally:
        selected_model.reset(token)
        model_errors.reset(errors)


def openai_payload(kwargs, model):
    messages = []
    if kwargs.get("system"):
        messages.append({"role": "system", "content": kwargs["system"]})
    for message in kwargs["messages"]:
        content = message["content"]
        if isinstance(content, str):
            messages.append({"role": message["role"], "content": content})
            continue
        texts, calls = [], []
        for block in content:
            block = block if isinstance(block, dict) else block.model_dump()
            if block["type"] == "text":
                texts.append(block["text"])
            elif block["type"] == "tool_use":
                calls.append({"id": block["id"], "type": "function", "function": {
                    "name": block["name"], "arguments": json.dumps(block["input"], ensure_ascii=False)}})
            elif block["type"] == "tool_result":
                value = block["content"]
                messages.append({"role": "tool", "tool_call_id": block["tool_use_id"],
                                 "content": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)})
        if texts or calls:
            row = {"role": message["role"], "content": "\n".join(texts) or None}
            if calls:
                row["tool_calls"] = calls
            messages.append(row)
    payload = {"model": model, "messages": messages, "max_tokens": kwargs.get("max_tokens", 2048),
               "temperature": kwargs.get("temperature", 0.3), "stream": False}
    if kwargs.get("tools"):
        payload["tools"] = [{"type": "function", "function": {"name": tool["name"],
                            "description": tool.get("description", ""), "parameters": tool["input_schema"]}}
                            for tool in kwargs["tools"]]
    return payload


class ScopedMessages(AsyncMessages):
    async def create(self, **kwargs):
        model = selected_model.get()
        if not model:
            return await super().create(**kwargs)
        try:
            response = await siliconflow.request("chat/completions", openai_payload(kwargs, model))
            message = response["choices"][0]["message"]
            blocks = []
            if message.get("content"):
                blocks.append({"type": "text", "text": message["content"]})
            for call in message.get("tool_calls") or []:
                arguments = json.loads(call["function"]["arguments"])
                if not isinstance(arguments, dict):
                    raise ValueError("invalid tool arguments")
                blocks.append({"type": "tool_use", "id": call["id"], "name": call["function"]["name"], "input": arguments})
            if not blocks:
                raise ValueError("empty response")
            return SimpleNamespace(content=blocks)
        except (HTTPException, ValueError, KeyError, IndexError, TypeError) as ex:
            error = ex if isinstance(ex, HTTPException) else HTTPException(502, "模型返回格式异常，请在模型中心检查该模型")
            errors = model_errors.get()
            if errors is not None:
                errors.append(error)
            raise error from None

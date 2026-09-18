"""Run two small model requests to verify Messages and tool-result compatibility."""

import asyncio
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from core.llm_utils import create_async_client, extract_text_content


async def main() -> int:
    load_dotenv(ROOT / ".env.local")
    load_dotenv(ROOT / ".env")
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    model = os.getenv("ANTHROPIC_MODEL", "").strip()
    base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip()
    print(f"Model: {model}; endpoint: {base_url}")
    try:
        async with create_async_client(key, base_url, timeout=45, max_retries=0) as client:
            messages = [{"role": "user", "content": "Call check_demo_status, then reply only OK if ready."}]
            tool = {"name": "check_demo_status", "description": "Check a harmless local demo status.",
                    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}}
            options = {"model": model, "max_tokens": 64, "temperature": 0,
                       "extra_body": {"thinking": {"type": "disabled"}}}
            first = await client.messages.create(
                **options, messages=messages, tools=[tool],
                tool_choice={"type": "tool", "name": "check_demo_status"},
            )
            calls = [b for b in first.content if getattr(b, "type", None) == "tool_use"]
            if not calls or any(b.name != "check_demo_status" for b in calls):
                print("FAIL: expected demo tool call was not returned")
                return 1
            messages.append({"role": "assistant", "content": [b.model_dump() for b in first.content]})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": b.id, "content": '{"ready": true}'} for b in calls
            ]})
            second = await client.messages.create(**options, messages=messages, tools=[tool])
            if not extract_text_content(second.content).strip():
                print("FAIL: model returned no final text")
                return 1
            print("PASS: Messages authentication, tool_use, tool_result and final text")
            print(f"Output tokens: {first.usage.output_tokens + second.usage.output_tokens}")
            print("Voucher deduction must be verified in the provider's billing console.")
            return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}; HTTP status={getattr(exc, 'status_code', 'n/a')}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

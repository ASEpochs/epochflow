"""Check local startup prerequisites without making paid model API calls."""

import importlib
import os
import pathlib
import sys

from dotenv import load_dotenv


ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    load_dotenv(ROOT / ".env.local")
    load_dotenv(ROOT / ".env")
    errors = []
    print(f"Python: {sys.executable}")

    for name in ("anthropic", "fastapi", "uvicorn", "redis", "chromadb", "onnxruntime"):
        try:
            importlib.import_module(name)
        except Exception as exc:
            errors.append(f"Dependency {name}: import failed ({type(exc).__name__})")

    key = os.getenv("ANTHROPIC_API_KEY", "").strip().strip("\"'")
    if not key or key.lower() in {"xxx", "your_key", "your_api_key", "changeme"} or key.lower().startswith("your_"):
        errors.append("ANTHROPIC_API_KEY: missing or placeholder; set a real key in .env.local")
    else:
        print("ANTHROPIC_API_KEY: present (not remotely validated)")

    if not os.getenv("ANTHROPIC_MODEL", "").strip():
        errors.append("ANTHROPIC_MODEL: missing; use a model supported by your provider")

    try:
        import redis

        client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        try:
            client.ping()
            print("Redis: connected")
        finally:
            client.close()
    except Exception as exc:
        errors.append(
            f"Redis: unavailable ({type(exc).__name__}); start Redis and check REDIS_URL/password"
        )

    print("ChromaDB: external server optional; application supports local persistent fallback")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print("Not ready for full chat. No model API requests were made.")
        return 1
    print("Local prerequisites ready. Model credentials still require an actual chat test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

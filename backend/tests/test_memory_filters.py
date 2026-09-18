import asyncio
from unittest.mock import AsyncMock

from chromadb.api.types import validate_where

from memory.conversation_memory import MemoryManager


def test_episodic_filters_are_valid_and_fallback_preserves_user_scope():
    manager = MemoryManager.__new__(MemoryManager)
    manager._query_episodic = AsyncMock(side_effect=[
        {"documents": [["current conversation"]]},
        {"documents": [["current conversation", "earlier conversation"]]},
    ])

    documents = asyncio.run(manager._search_episodic("demo_user", "demo_conv", "hello"))

    assert documents == ["current conversation", "earlier conversation"]
    filters = [call.kwargs["where"] for call in manager._query_episodic.await_args_list]
    assert filters == [
        {"$and": [{"user_id": "demo_user"}, {"conv_id": "demo_conv"}]},
        {"user_id": "demo_user"},
    ]
    for where in filters:
        validate_where(where)


def test_empty_episodic_query_does_not_query_database():
    manager = MemoryManager.__new__(MemoryManager)
    manager._query_episodic = AsyncMock()

    assert asyncio.run(manager._search_episodic("demo_user", "demo_conv", "  ")) == []
    manager._query_episodic.assert_not_awaited()

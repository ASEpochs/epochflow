"""Bounded, process-local working memory for the free deployment profile."""
import time
from collections import OrderedDict

from memory.models import Message, MemoryContext


class MemoryManager:
    MAX_SESSIONS = 100
    MAX_MESSAGES = 20
    TTL_SECONDS = 3600

    def __init__(self, **kwargs):
        self._sessions = OrderedDict()

    def _session(self, user_id, conv_id):
        now = time.monotonic()
        for key, (_, updated) in list(self._sessions.items()):
            if now - updated >= self.TTL_SECONDS:
                del self._sessions[key]
        key = (user_id, conv_id)
        messages, _ = self._sessions.pop(key, ([], now))
        self._sessions[key] = (messages, now)
        while len(self._sessions) > self.MAX_SESSIONS:
            self._sessions.popitem(last=False)
        return messages

    async def add_message(self, user_id, conv_id, role, content, metadata=None):
        messages = self._session(user_id, conv_id)
        messages.append(Message(role=role, content=content[:8000], metadata=metadata or {}))
        del messages[:-self.MAX_MESSAGES]

    async def get_context(self, user_id, conv_id, query=""):
        return MemoryContext(
            recent_messages=list(self._session(user_id, conv_id)),
            relevant_history=[], user_profile={}, summary="",
        )

    async def update_profile(self, user_id, conv_id):
        # Free mode deliberately does not infer or store cross-session profiles.
        return None

    async def close(self):
        self._sessions.clear()

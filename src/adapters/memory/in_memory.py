from __future__ import annotations
"""In-memory conversation memory.

Provides a simple per-session memory handle that stores:
- `history`: list of messages (dicts)
- `params`: accumulated intent parameters across turns
- `waiting`: name of the parameter the agent is waiting for (if any)

Intended for local development and tests. Swap with a SQLite-backed provider
without changing Router code by preserving the `SessionMemoryHandle` interface.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from src.core.interfaces import ConversationMemory, SessionMemoryHandle


@dataclass
class _Session(SessionMemoryHandle):
    session_id: str
    max_messages: int = 10
    _history: List[dict] = field(default_factory=list)
    _params: Dict[str, str] = field(default_factory=dict)
    _waiting: Optional[str] = None

    def history(self) -> List[dict]:
        return list(self._history)

    def append(self, message: dict) -> None:
        self._history.append(message)
        self.prune(self.max_messages)

    def params(self) -> Dict[str, str]:
        return dict(self._params)

    def merge(self, params: Dict[str, str]) -> None:
        self._params.update(params or {})

    def waiting(self) -> str | None:
        return self._waiting

    def set_waiting(self, name: str | None) -> None:
        self._waiting = name

    def prune(self, max_messages: int = 10) -> None:
        if max_messages > 0 and len(self._history) > max_messages:
            # Keep the most recent `max_messages` entries
            self._history = self._history[-max_messages:]

    def clear(self) -> None:
        self._history.clear()
        self._params.clear()
        self._waiting = None


class InMemoryConversationMemory(ConversationMemory):
    """Simple in-process memory implementation.

    Stores session state in a dict; not suitable for multi-process or long-term
    persistence, but fast and dependency-free for development.
    """

    def __init__(self, max_messages: int = 10) -> None:
        self._max_messages = max_messages
        self._sessions: Dict[str, _Session] = {}

    def for_session(self, session_id: str) -> SessionMemoryHandle:
        if session_id not in self._sessions:
            self._sessions[session_id] = _Session(session_id=session_id, max_messages=self._max_messages)
        return self._sessions[session_id]


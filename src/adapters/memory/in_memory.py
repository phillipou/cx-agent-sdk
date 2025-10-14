from __future__ import annotations
"""In-memory implementation of ConversationMemory (Session handle façade).

This keeps per-session history, parameters, and a single waiting-for-param flag
so the agent can run multi-turn flows without persistence. Designed for M1.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import datetime

from src.core.interfaces import ConversationMemory, SessionMemoryHandle


def _now_iso() -> str:
    """Return a UTC ISO8601 timestamp string.

    Used to stamp messages that don't provide a timestamp so history
    entries are always time-ordered and traceable in telemetry.
    """
    return datetime.utcnow().isoformat() + "Z"


@dataclass
class _SessionState:
    """Internal container for per-session state.

    - history: chronological list of messages exchanged in the session
    - params: accumulated intent parameters extracted across turns
    - waiting_for_param: the single parameter name we are currently asking for
    - last_intent_id: most recent classified intent (optional, for analytics)
    - last_result: most recent tool result summary (optional)
    """

    history: List[dict] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    waiting_for_param: str | None = None
    last_intent_id: str | None = None
    last_result: Dict[str, Any] | None = None


class InMemoryConversationMemory(ConversationMemory):
    """Dict-backed session memory with simple pruning.

    Notes
    - In-memory only: state resets when the process restarts.
    - Not thread-safe: suitable for local/dev flows in Milestone 1.
    - Use `for_session()` to obtain a per-session handle that exposes
      ergonomic methods (history/params/waiting/prune/clear).
    """

    def __init__(self, max_messages: int = 10) -> None:
        self._sessions: Dict[str, _SessionState] = {}
        self._max_messages = max_messages

    def _ensure(self, sid: str) -> _SessionState:
        """Create and return the session state if it does not exist.

        This guarantees a valid state object for all subsequent operations
        and centralizes initialization defaults.
        """
        if sid not in self._sessions:
            self._sessions[sid] = _SessionState()
        return self._sessions[sid]

    class _Handle(SessionMemoryHandle):
        def __init__(self, outer: "InMemoryConversationMemory", sid: str) -> None:
            self._outer = outer
            self._sid = sid

        def history(self) -> List[dict]:
            """Return a copy of chronological messages for the session.

            A copy is returned to avoid accidental mutation of internal state.
            """
            return list(self._outer._ensure(self._sid).history)

        def append(self, message: dict) -> None:
            """Append a message to the session history and enforce pruning.

            If the message lacks a `timestamp`, one is injected so downstream
            consumers (telemetry/UX) can reliably order events.
            """
            st = self._outer._ensure(self._sid)
            if "timestamp" not in message:
                message = {**message, "timestamp": _now_iso()}
            st.history.append(message)
            self.prune(self._outer._max_messages)

        def params(self) -> Dict[str, Any]:
            """Return a shallow copy of accumulated intent parameters."""
            return dict(self._outer._ensure(self._sid).params)

        def merge(self, params: Dict[str, Any]) -> None:
            """Merge new parameters into the session's parameter map.

            Existing keys are overwritten; call-sites should pass normalized
            values (e.g., trimmed/validated) when possible.
            """
            st = self._outer._ensure(self._sid)
            st.params.update(params or {})

        def waiting(self) -> str | None:
            """Return the name of the parameter the agent is waiting for, if any."""
            return self._outer._ensure(self._sid).waiting_for_param

        def set_waiting(self, name: str | None) -> None:
            """Set or clear the waiting-for-param flag for this session."""
            self._outer._ensure(self._sid).waiting_for_param = name

        def prune(self, max_messages: int = 10) -> None:
            """Keep only the most recent `max_messages` entries in history.

            This is a simple proxy for token-budget control. A token-aware
            strategy can replace this in a future milestone.
            """
            st = self._outer._ensure(self._sid)
            if len(st.history) > max_messages:
                st.history = st.history[-max_messages:]

        def clear(self) -> None:
            """Delete all state for this session (history, params, flags)."""
            if self._sid in self._outer._sessions:
                del self._outer._sessions[self._sid]

    def for_session(self, session_id: str) -> SessionMemoryHandle:
        """Return a session-scoped handle for convenient memory operations.

        Ensures the session state exists, then exposes a façade with
        readable methods (history/params/waiting/prune/clear) so
        orchestrator code stays concise and intention-revealing.
        """
        self._ensure(session_id)
        return InMemoryConversationMemory._Handle(self, session_id)

from __future__ import annotations
"""Local tool executor.

Maintains an in-process registry of tool handlers (callables) keyed by name
and invokes them with validated parameters from the policy stage.
"""
from src.core.interfaces import ToolExecutor
from src.core.types import ToolResult, ToolCall


class LocalExecutor(ToolExecutor):
    def __init__(self) -> None:
        self._handlers: dict[str, callable] = {}

    def register(self, tool_name: str, handler) -> None:
        self._handlers[tool_name] = handler

    def execute(self, call: ToolCall) -> ToolResult:
        """Invoke the registered tool handler for the given call.

        Returns a structured `ToolResult` with either `ok=True, data=...` or
        `ok=False, error=...`.
        """
        fn = self._handlers.get(call["tool_name"])  # type: ignore
        if not fn:
            return {"ok": False, "error": "unknown_tool"}
        return fn(call.get("params", {}))

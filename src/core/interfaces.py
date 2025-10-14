from __future__ import annotations
"""Interface definitions for the agent's swappable primitives.

These `Protocol`s define boundaries so implementations can be swapped without
changing orchestration logic (e.g., JSON vs. SQL data source, different LLMs,
local vs. remote executors, etc.).
"""
from typing import Protocol, Any
from .types import (
    Interaction,
    ToolCall,
    PolicyDecision,
    ToolResult,
    TelemetryEvent,
    Intent,
    Plan,
)


class DataSource(Protocol):
    """Abstracts access to domain data (orders, customers, tickets)."""
    def get_order(self, order_id: str) -> dict | None: ...


class LLMProvider(Protocol):
    """Low-level LLM interface. Concrete providers wrap OpenAI/Anthropic/etc.

    For M1, we primarily use `generate` to support LLM-based classification.
    `route` exists for backward compatibility but is not used here.
    """

    def generate(self, messages: list[dict], response_format: dict | None = None) -> dict: ...

    def route(self, interaction: Interaction, history: list[dict]) -> ToolCall: ...


class PolicyEngine(Protocol):
    def validate(
        self, call: ToolCall, interaction: Interaction, history: list[dict]
    ) -> PolicyDecision: ...


class ToolExecutor(Protocol):
    """Executes registered tool handlers with validated parameters."""
    def register(self, tool_name: str, handler) -> None: ...
    def execute(self, call: ToolCall) -> ToolResult: ...


class TelemetrySink(Protocol):
    """Records structured events for observability and evaluation."""
    def record(self, event: TelemetryEvent) -> None: ...


class IntentsRegistry(Protocol):
    """Provides the set of intents eligible for the current context."""
    def get_eligible(self, context: dict) -> list[Intent]: ...


class IntentClassifier(Protocol):
    """Maps a user interaction to an eligible intent and extracts intent parameters."""
    def classify(
        self, interaction: Interaction, intents: list[Intent], history: list[dict]
    ) -> tuple[Intent | None, dict]: ...


class Planner(Protocol):
    """Converts a chosen intent + parameters into an executable plan (steps)."""
    def plan(self, intent: Intent, interaction: Interaction, params: dict) -> Plan: ...


class SessionMemoryHandle(Protocol):
    """Ergonomic per-session memory API (Option A: Session handle façade).

    Keeps history, parameters, and the waiting-for-param flag together so Router
    code remains readable. Implementations can back this with dicts or a DB.
    """

    def history(self) -> list[dict]: ...
    def append(self, message: dict) -> None: ...

    def params(self) -> dict: ...
    def merge(self, params: dict) -> None: ...

    def waiting(self) -> str | None: ...
    def set_waiting(self, name: str | None) -> None: ...

    def prune(self, max_messages: int = 10) -> None: ...
    def clear(self) -> None: ...


class ConversationMemory(Protocol):
    """Factory for per-session memory handles."""

    def for_session(self, session_id: str) -> SessionMemoryHandle: ...

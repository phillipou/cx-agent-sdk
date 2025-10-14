from __future__ import annotations
"""Null policy engine.

Accepts all tool calls. Useful for development before implementing real rules
or approvals.
"""
from src.core.interfaces import PolicyEngine
from src.core.types import ToolCall, Interaction, PolicyDecision


class NullPolicyEngine(PolicyEngine):
    def validate(self, call: ToolCall, interaction: Interaction, history: list[dict]) -> PolicyDecision:
        return PolicyDecision(allowed=True, reasons=[])

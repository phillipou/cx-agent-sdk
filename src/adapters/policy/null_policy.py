from __future__ import annotations
from src.core.interfaces import PolicyEngine
from src.core.types import ToolCall, Interaction, PolicyDecision


class NullPolicyEngine(PolicyEngine):
    def validate(self, call: ToolCall, interaction: Interaction, history: list[dict]) -> PolicyDecision:
        return PolicyDecision(allowed=True, reasons=[])


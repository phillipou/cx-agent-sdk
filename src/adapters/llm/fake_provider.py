from __future__ import annotations
import re
from typing import Dict, Any, List

from src.core.interfaces import LLMProvider


class FakeLLMProvider(LLMProvider):
    """A local, deterministic LLM stand-in used for tests and demos.

    - Ignores model/network and returns a structured dict mimicking an LLM JSON response.
    - Looks for an order-like token in the last user message to simulate parameter extraction.
    - This lets us exercise the LLM-based classifier without external dependencies or cost.
    """

    ORDER_RE = re.compile(r"(?i)\bO-\d+\b")

    def generate(self, messages: List[Dict[str, Any]], response_format: dict | None = None) -> dict:
        """Return a deterministic, JSON-like classification result for tests.

        Extracts an order-like token from the last user message and fabricates
        an object that mirrors the real provider's response shape.
        """
        # Find the latest user message content
        user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_text = m.get("content", "")
                break

        # Simple heuristic to simulate intent and parameter extraction
        order_id = None
        m = self.ORDER_RE.search(user_text or "")
        if m:
            order_id = m.group(0)

        # Assume the only eligible intent in M1 is order_status
        intent_id = "order_status" if ("order" in (user_text or "").lower()) else None

        return {
            "intent_id": intent_id,
            "params": {"order_id": order_id} if order_id else {},
            "missing_params": [] if order_id else ["order_id"] if intent_id else [],
            "confidence": 0.9 if intent_id else 0.0,
        }

    # Not used in M1; present for interface compatibility
    def route(self, interaction, history):  # pragma: no cover - unused stub
        """Compatibility stub; not used by the M1 router."""
        return {"tool_name": "", "params": {}}

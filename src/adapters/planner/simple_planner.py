from __future__ import annotations
"""Simple planner.

Translates a chosen intent + slots into a small, linear plan:
  1) pre `Respond` message (tell the user what will happen)
  2) `ToolCall` with the chosen tool and extracted params
  3) post `Respond` template containing a `{summary}` placeholder
"""
from typing import List
from src.core.interfaces import Planner
from src.core.types import Intent, Interaction, Plan, Respond, ToolCall


class SimplePlanner(Planner):
    def plan(self, intent: Intent, interaction: Interaction, params: dict) -> Plan:
        """Create a minimal plan: Respond(pre) → ToolCall → Respond(post).

        The post response includes a `{summary}` placeholder that the router
        replaces after the tool executes.
        """
        intent_id = intent.get("id", "")
        steps: List[dict] = []
        # Pre-respond
        order_id = params.get("order_id")
        pre_msg = (
            f"I’ll check the status of order {order_id}."
            if order_id
            else "I’ll check your order status."
        )
        steps.append(Respond(type="respond", when="pre", message=pre_msg))

        # Tool step
        tool_name = intent.get("tool") or ""
        tool_params = {**params}
        steps.append(ToolCall(tool_name=tool_name, params=tool_params))

        # Post-respond template (planner does not know result yet)
        post_msg = (
            f"Here’s what I found for order {order_id}: {{summary}}"
            if order_id
            else "Here’s what I found: {summary}"
        )
        steps.append(Respond(type="respond", when="post", message=post_msg))

        return Plan(intent_id=intent_id, steps=steps)

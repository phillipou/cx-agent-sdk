from __future__ import annotations
from typing import List
from src.core.types import (
    Interaction,
    AgentResponse,
    TelemetryEvent,
    ToolCall,
    Plan,
    Respond,
)
from src.core.interfaces import (
    IntentsRegistry,
    IntentClassifier,
    Planner,
    PolicyEngine,
    ToolExecutor,
    TelemetrySink,
)


class AgentRouter:
    """Coordinates the end-to-end flow: intents → classify → plan → policy → tools → respond.

    M1 keeps state in memory and emits telemetry so behavior is easy to follow.
    """
    def __init__(
        self,
        intents: IntentsRegistry,
        classifier: IntentClassifier,
        planner: Planner,
        policy: PolicyEngine,
        executor: ToolExecutor,
        telemetry: TelemetrySink,
    ) -> None:
        self.intents = intents
        self.classifier = classifier
        self.planner = planner
        self.policy = policy
        self.executor = executor
        self.telemetry = telemetry
        self._history: dict[str, List[dict]] = {}

    def handle(self, interaction: Interaction) -> AgentResponse:
        # Derive a session id and fetch prior messages (if any)
        session_id = interaction.get("context", {}).get("session_id", interaction.get("id", ""))
        history = self._history.get(session_id, [])

        # 1) Record receipt of the message
        self.telemetry.record(
            TelemetryEvent(
                timestamp="",
                interaction_id=interaction.get("id", ""),
                session_id=session_id,
                stage="received",
                level="info",
                payload={},
            )
        )

        # 2) Determine eligible intents from config/context
        eligible = self.intents.get_eligible(interaction.get("context", {}))
        self.telemetry.record(
            TelemetryEvent(
                timestamp="",
                interaction_id=interaction.get("id", ""),
                session_id=session_id,
                stage="intents_eligible",
                level="info",
                payload={"eligible": [it.get("id") for it in eligible]},
            )
        )

        # 3) LLM-based classification to pick intent and extract slots
        intent, slots = self.classifier.classify(interaction, eligible, history)
        if not intent:
            # No supported intent → clarify politely
            msg = "I didn’t recognize a supported request. For now I can check order status."
            return AgentResponse(text=msg)
        self.telemetry.record(
            TelemetryEvent(
                timestamp="",
                interaction_id=interaction.get("id", ""),
                session_id=session_id,
                stage="intent_classified",
                level="info",
                payload={"intent_id": intent.get("id"), "slots_redacted": list(slots.keys())},
            )
        )

        # 4) Build a plan with pre/post Respond steps and a ToolCall
        plan: Plan = self.planner.plan(intent, interaction, slots)
        self.telemetry.record(
            TelemetryEvent(
                timestamp="",
                interaction_id=interaction.get("id", ""),
                session_id=session_id,
                stage="plan_created",
                level="info",
                payload={"intent_id": intent.get("id"), "steps": [s.get("type", "tool_call") if isinstance(s, dict) and "type" in s else "tool_call" for s in plan["steps"]]},
            )
        )

        # 5) Communicate the plan (pre-respond) to the user
        pre = next((s for s in plan["steps"] if isinstance(s, dict) and s.get("type") == "respond" and s.get("when") == "pre"), None)
        pre_text = pre.get("message") if pre else None
        if pre_text:
            self.telemetry.record(
                TelemetryEvent(
                    timestamp="",
                    interaction_id=interaction.get("id", ""),
                    session_id=session_id,
                    stage="plan_communicated",
                    level="info",
                    payload={"message": pre_text},
                )
            )

        # 6) Execute the tool step (single ToolCall for M1)
        tool_step = next((s for s in plan["steps"] if not isinstance(s, dict) or "type" not in s), None)
        result_text = ""
        tool_result = None
        if tool_step:
            call: ToolCall = tool_step  # type: ignore
            # Validate via policy (NullPolicyEngine allows all)
            decision = self.policy.validate(call, interaction, history)
            self.telemetry.record(
                TelemetryEvent(
                    timestamp="",
                    interaction_id=interaction.get("id", ""),
                    session_id=session_id,
                    stage="policy_check",
                    level="info",
                    payload={"allowed": decision.get("allowed", True)},
                )
            )
            if decision.get("allowed", True):
                tool_result = self.executor.execute(call)
                self.telemetry.record(
                    TelemetryEvent(
                        timestamp="",
                        interaction_id=interaction.get("id", ""),
                        session_id=session_id,
                        stage="tool_execute",
                        level="info",
                        payload={"ok": tool_result.get("ok", False), "tool": call.get("tool_name")},
                    )
                )
                # Summarize the result for the post message
                if tool_result.get("ok") and tool_result.get("data"):
                    data = tool_result.get("data", {})
                    result_text = _format_order_status_summary(data)
                else:
                    result_text = "I couldn’t find that order."
            else:
                result_text = "This action isn’t allowed by policy."

        # 7) Build the final response using the post-respond template
        post = next((s for s in plan["steps"] if isinstance(s, dict) and s.get("type") == "respond" and s.get("when") == "post"), None)
        final_text = (post.get("message") or "Here’s the result: {summary}").replace("{summary}", result_text) if post else result_text

        # 8) Emit final telemetry and return
        self.telemetry.record(
            TelemetryEvent(
                timestamp="",
                interaction_id=interaction.get("id", ""),
                session_id=session_id,
                stage="respond",
                level="info",
                payload={"message": final_text},
            )
        )

        return AgentResponse(text=final_text, tool_result=tool_result)


def _format_order_status_summary(order: dict) -> str:
    """Create a short, human-friendly summary from an order record."""
    status = order.get("status", "unknown").replace("_", " ")
    carrier = order.get("carrier")
    eta = order.get("eta") or order.get("delivered_at")
    parts = [f"status: {status}"]
    if carrier:
        parts.append(f"carrier: {carrier}")
    if eta:
        parts.append(f"ETA: {eta}")
    return ", ".join(parts)


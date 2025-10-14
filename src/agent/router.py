from __future__ import annotations
"""Agent router orchestrates the end-to-end flow.

Flow summary:
  received → intents_eligible → intent_classified → plan_created → plan_communicated
  → policy_check → tool_execute → respond

This module keeps memory in-process (by session id) and emits structured
telemetry at each stage via the provided `TelemetrySink`.
"""
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
    ConversationMemory,
)


class AgentRouter:
    """Coordinates: intents → classify → plan → policy → tools → respond.

    Minimal state and simple summarization make behavior easy to inspect while
    preserving component boundaries (policy, tools, telemetry, etc.).
    """
    def __init__(
        self,
        intents: IntentsRegistry,
        classifier: IntentClassifier,
        planner: Planner,
        policy: PolicyEngine,
        executor: ToolExecutor,
        telemetry: TelemetrySink,
        memory: ConversationMemory,
    ) -> None:
        """Construct the router with swappable components.

        Each dependency implements a `Protocol` so adapters can be swapped
        without changing orchestration logic.
        """
        self.intents = intents
        self.classifier = classifier
        self.planner = planner
        self.policy = policy
        self.executor = executor
        self.telemetry = telemetry
        self.memory = memory

    def handle(self, interaction: Interaction) -> AgentResponse:
        """Process a single user interaction and return a response.

        Decomposed into small helpers to keep orchestration readable and testable.
        """
        session_id, sesh, history = self._init_session(interaction)
        eligible = self._eligible_intents(interaction, session_id)
        intent, _ = self._classify_and_merge(interaction, eligible, history, sesh, session_id)
        if not intent:
            return AgentResponse(text="I didn’t recognize a supported request. For now I can check order status.")
        plan = self._create_plan(intent, interaction, sesh, session_id)
        ask_resp = self._maybe_ask_user(plan, interaction, session_id, sesh)
        if ask_resp:
            return ask_resp
        self._emit_pre_response(plan, interaction, session_id)
        tool_result, result_text = self._execute_tool_step(plan, interaction, history, session_id)
        final_text = self._build_final_text(plan, result_text)
        self._emit_final_response(interaction, session_id, sesh, final_text)
        return AgentResponse(text=final_text, tool_result=tool_result)

    # --- Helpers ---

    def _init_session(self, interaction: Interaction):
        session_id = interaction.get("context", {}).get("session_id", interaction.get("id", ""))
        sesh = self.memory.for_session(session_id)
        sesh.append({"role": "user", "text": interaction.get("text", ""), "metadata": {}})
        history = sesh.history()
        self.telemetry.record(
            TelemetryEvent(
                timestamp="",
                interaction_id=interaction.get("id", ""),
                session_id=session_id,
                stage="received",
                level="info",
                payload={
                    "memory": {
                        "history_count": len(history),
                        "params_keys": list(sesh.params().keys()),
                        "waiting_for_param": sesh.waiting(),
                    }
                },
            )
        )
        return session_id, sesh, history

    def _eligible_intents(self, interaction: Interaction, session_id: str):
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
        return eligible

    def _classify_and_merge(self, interaction: Interaction, intents: List[dict], history: List[dict], sesh, session_id: str):
        intent, params = self.classifier.classify(interaction, intents, history)
        if params:
            sesh.merge(params)
        if sesh.waiting() and params.get(sesh.waiting() or ""):
            sesh.set_waiting(None)
        if intent:
            self.telemetry.record(
                TelemetryEvent(
                    timestamp="",
                    interaction_id=interaction.get("id", ""),
                    session_id=session_id,
                    stage="intent_classified",
                    level="info",
                    payload={"intent_id": intent.get("id"), "redacted_params": list(sesh.params().keys())},
                )
            )
        return intent, params

    def _create_plan(self, intent, interaction, sesh, session_id: str) -> Plan:
        plan: Plan = self.planner.plan(intent, interaction, sesh.params())
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
        return plan

    def _maybe_ask_user(self, plan: Plan, interaction: Interaction, session_id: str, sesh):
        ask = next((s for s in plan["steps"] if isinstance(s, dict) and s.get("type") == "ask_user"), None)
        if not ask:
            return None
        missing_param = ask.get("param")
        prompt = ask.get("prompt") or "Could you provide the missing information?"
        sesh.set_waiting(missing_param)
        self.telemetry.record(
            TelemetryEvent(
                timestamp="",
                interaction_id=interaction.get("id", ""),
                session_id=session_id,
                stage="respond",
                level="info",
                payload={"message": prompt, "waiting_for_param": missing_param},
            )
        )
        sesh.append({"role": "agent", "text": prompt, "metadata": {"type": "ask_user", "param": missing_param}})
        return AgentResponse(text=prompt)

    def _emit_pre_response(self, plan: Plan, interaction: Interaction, session_id: str) -> None:
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

    def _execute_tool_step(self, plan: Plan, interaction: Interaction, history: List[dict], session_id: str):
        tool_step = next((s for s in plan["steps"] if not isinstance(s, dict) or "type" not in s), None)
        result_text = ""
        tool_result = None
        if tool_step:
            call: ToolCall = tool_step  # type: ignore
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
                if tool_result.get("ok") and tool_result.get("data"):
                    data = tool_result.get("data", {})
                    result_text = _format_order_status_summary(data)
                else:
                    result_text = "I couldn’t find that order."
            else:
                result_text = "This action isn’t allowed by policy."
        return tool_result, result_text

    def _build_final_text(self, plan: Plan, result_text: str) -> str:
        post = next((s for s in plan["steps"] if isinstance(s, dict) and s.get("type") == "respond" and s.get("when") == "post"), None)
        return (post.get("message") or "Here’s the result: {summary}").replace("{summary}", result_text) if post else result_text

    def _emit_final_response(self, interaction: Interaction, session_id: str, sesh, final_text: str) -> None:
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
        sesh.append({"role": "agent", "text": final_text, "metadata": {}})


def _format_order_status_summary(order: dict) -> str:
    """Create a short, human-friendly summary from an order record.

    This is domain-specific for the demo. Real systems likely render richer
    content or defer formatting to a response template system.
    """
    status = order.get("status", "unknown").replace("_", " ")
    carrier = order.get("carrier")
    eta = order.get("eta") or order.get("delivered_at")
    parts = [f"status: {status}"]
    if carrier:
        parts.append(f"carrier: {carrier}")
    if eta:
        parts.append(f"ETA: {eta}")
    return ", ".join(parts)

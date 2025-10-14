from __future__ import annotations
"""Shared type definitions used across the agent.

The project favors simple, explicit `TypedDict` structures for message passing
between components. This keeps adapters loosely coupled and easy to test.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict, Literal


class Interaction(TypedDict, total=False):
    id: str
    text: str
    customer_id: Optional[str]
    context: Dict[str, Any]


class ToolCall(TypedDict):
    tool_name: Literal["check_order_status"]
    params: Dict[str, Any]


class PolicyDecision(TypedDict):
    allowed: bool
    reasons: List[str]


class ToolResult(TypedDict, total=False):
    ok: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]


class AgentResponse(TypedDict, total=False):
    text: str
    tool_result: Optional[ToolResult]


class Intent(TypedDict, total=False):
    id: str
    description: str
    required_params: List[str]
    tool: str
    param_mapping: Dict[str, str]
    constraints: Dict[str, Any]
    redaction: Dict[str, Any]


class AskUser(TypedDict):
    type: Literal["ask_user"]
    param: str
    prompt: str


class Respond(TypedDict):
    type: Literal["respond"]
    when: Literal["pre", "post", "error"]
    message: str


PlanStep = ToolCall | AskUser | Respond


class Plan(TypedDict):
    intent_id: str
    steps: List[PlanStep]


class TelemetryEvent(TypedDict, total=False):
    timestamp: str
    interaction_id: str
    session_id: str
    stage: Literal[
        "received",
        "intents_eligible",
        "intent_classified",
        "plan_created",
        "plan_communicated",
        "policy_check",
        "tool_execute",
        "respond",
    ]
    level: Literal["info", "warn", "error"]
    payload: Dict[str, Any]


StepStatus = Literal[
    "pending",
    "in_progress",
    "completed",
    "failed",
    "blocked",
    "waiting_user",
    "canceled",
]


class PlanExecutionStep(TypedDict, total=False):
    step: PlanStep
    status: StepStatus
    started_at: Optional[str]
    ended_at: Optional[str]
    error: Optional[str]


class PlanExecution(TypedDict, total=False):
    plan_id: str
    intent_id: str
    steps: List[PlanExecutionStep]
    current_index: int

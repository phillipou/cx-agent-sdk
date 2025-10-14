# Design: Agent Router Orchestration

## Summary
The Agent Router coordinates the end-to-end flow for a customer interaction:
received → intents_eligible → intent_classified → plan_created → plan_communicated →
policy_check → tool_execute → respond. It composes swappable primitives
(IntentsRegistry, IntentClassifier, Planner, PolicyEngine, ToolExecutor,
TelemetrySink, ConversationMemory) while keeping orchestration logic slim and
observable. Goals: clear boundaries, structured telemetry, multi-turn support,
and safe fallbacks.

Primary implementation: `src/agent/router.py`.

## Goals
- Separation of concerns: Orchestration doesn’t embed business logic.
- Swappable primitives: Swap LLM/DataSource/Policy without changing the router.
- Deterministic, structured telemetry for each stage (traceability-by-default).
- Multi-turn support via explicit `ConversationMemory` integration.
- Slot filling via `AskUser` planning step and resume-on-reply.
- Safe fallbacks on unknown/unsupported intents or errors.
- Testability with mocked adapters (e.g., LLM, DataSource, Policy, Telemetry).

## Non-Goals
- UI, persistence, or dashboards (handled by Streamlit apps + sinks).
- Defining policy rules or tool schemas (owned by adapters/config).
- Production concerns (auth, rate-limits, distributed memory, retries infra).

## Architecture & Components
- IntentsRegistry: returns eligible intents from config by context (channel, rollout).
- IntentClassifier: LLM-powered mapping of interaction → intent + slots.
- Planner: Converts chosen intent + slots into a `Plan` with steps:
  - `Respond(pre)` → `ToolCall` → `Respond(post)` (M1)
  - Later: `AskUser` when required slots are missing.
- PolicyEngine: Validates a tool invocation against rules (M1 uses NullPolicy).
- ToolExecutor: Invokes registered tool handlers with validated params.
- TelemetrySink: Records structured telemetry at each router stage.
- ConversationMemory: Provides per-session history and context to classifier/policy.

Sequence (M1 baseline):
1) received: record; derive `session_id`; load history (in-memory).
2) intents_eligible: query registry based on `interaction.context`.
3) intent_classified: LLM classify intent + extract slots.
4) plan_created: planner emits Respond(pre), ToolCall, Respond(post).
5) plan_communicated: emit pre message via telemetry (and optionally UI).
6) policy_check: validate `ToolCall` (allow/deny with reasons).
7) tool_execute: execute handler; summarize result for post message.
8) respond: emit final message; update memory (future: append interaction + response).

## Data & Schemas
- `Interaction`: `{id, text, customer_id?, context}` (see `src/core/types.py`).
- `Plan`: `{intent_id, steps: List[PlanStep]}`
  - `PlanStep` ∈ `ToolCall | AskUser | Respond`.
- `TelemetryEvent`: stage ∈ {received, intents_eligible, intent_classified, plan_created,
  plan_communicated, policy_check, tool_execute, respond}; payload is structured.
- `PlanExecution` (planned): per-step `status` (pending/in_progress/completed/failed) with timestamps.

## APIs & Interfaces
Router constructor:
```
AgentRouter(
  intents: IntentsRegistry,
  classifier: IntentClassifier,
  planner: Planner,
  policy: PolicyEngine,
  executor: ToolExecutor,
  telemetry: TelemetrySink,
  # memory: ConversationMemory (planned; currently in-memory placeholder)
)
```

Primary entrypoint:
- `handle(interaction: Interaction) -> AgentResponse`
  - Drives the sequence above, emits telemetry, and returns `{text, tool_result?}`.

Referenced protocols: see `src/core/interfaces.py`.

## Policies, Memory, Evaluation
- Policy: Router defers to `PolicyEngine.validate(call, interaction, history)` and logs the outcome. M1 uses `NullPolicyEngine` (allow-all), Milestone 3 will replace with YAML-driven engine.
- Memory: Router keys memory by `session_id` (from `interaction.context` or `id`).
  - M1.1: integrate `ConversationMemory` to load/append/clear; include `history_loaded` and `memory_updated` telemetry.
  - Classifier may use history to extract missing slots or disambiguate intents.
- Evaluation: Telemetry provides a trace for deterministic evals; later, an `SQLiteSink` will persist events for dashboards and harness.

## Risks & Mitigations
- LLM variability: Enforce JSON response format; validate/guard output; add retries/backoff.
- Slot collection loops: Use `AskUser` with explicit missing slot names; persist state in memory; cap clarification turns; provide safe fallback.
- Privacy/PII: Redact sensitive slots in telemetry per `config/intents.yaml` redaction rules.
- Tool errors: Standardize `ToolResult` with `ok|error`; map errors to friendly copy.
- Coupling creep: Keep router thin; push business logic to adapters/tools.

## Milestones
- M1 (current): Single ToolCall path with pre/post respond; basic telemetry; allow-all policy.
- M1.1 (next):
  - Wire `ConversationMemory` Protocol + `InMemoryConversationMemory` into router.
  - `AskUser` support in planner + router; waiting_user status and resume flow.
  - PlanRunner: per-step status + timestamps; per-step telemetry payloads.
  - Telemetry polish: timestamps; redaction; include `intent_id` across events.
- M2: Expand tools (refund, create_ticket, escalate) and intents; enrich data fixtures.
- M3: YAMLPolicyEngine; enforce policies with composable conditions; log violations.
- M4: Evaluation harness + SQLite sink; golden YAML; CLI `scripts/run_eval.py`.

## Open Questions
- Multi-step plans: Should we allow multiple ToolCalls per plan in M1 or defer?
- Streaming: Do we stream pre/post messages to the UI or return as a single response?
- Memory scope: In-memory only for M1 or add optional SQLite-backed memory?
- Model selection: Per-intent/per-step models vs per-agent default (currently per-agent parameter).
- Error taxonomy: Standardize error codes for tools/policies for easier eval and UI mapping.


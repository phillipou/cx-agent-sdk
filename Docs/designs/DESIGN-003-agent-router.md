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
- IntentClassifier: LLM-powered mapping of interaction → intent + parameters.
- Planner: Converts chosen intent + parameters into a `Plan` with steps:
  - `Respond(pre)` → `ToolCall` → `Respond(post)` (M1)
  - `AskUser` when required parameters are missing (M1.1): emits `{type: "ask_user", param, prompt}` and returns early (no tool call).
- PolicyEngine: Validates a tool invocation against rules (M1 uses NullPolicy).
- ToolExecutor: Invokes registered tool handlers with validated params.
- TelemetrySink: Records structured telemetry at each router stage.
- ConversationMemory: Provides per-session history and context to classifier/policy.

Sequence (M1 baseline):
1) received: record; derive `session_id`; load history (in-memory).
2) intents_eligible: query registry based on `interaction.context`.
3) intent_classified: LLM classify intent + extract parameters.
4) plan_created: planner emits Respond(pre), ToolCall, Respond(post).
5) plan_communicated: emit pre message via telemetry (and optionally UI).
6) policy_check: validate `ToolCall` (allow/deny with reasons).
7) tool_execute: execute handler; summarize result for post message.
8) respond: emit final message; update memory (future: append interaction + response).

Unknown intent (M1.1):
- If no intent is classified, the Router:
  - Emits `intent_classified` with `{intent_id: null, unknown_intent: true}`.
  - Uses the classifier’s LLM provider to draft a short clarification that ALWAYS ends with: "Would you like me to loop in a human support agent?"; on failure, falls back to a deterministic line with that sentence.
  - Appends the message to memory and emits `respond` with `{fallback: true, unknown_intent: true}`.

## Data & Schemas
- `Interaction`: `{id, text, customer_id?, context}` (see `src/core/types.py`).
- `Plan`: `{intent_id, steps: List[PlanStep]}`
  - `PlanStep` ∈ `ToolCall | AskUser | Respond`.
  - `AskUser`: `{type: "ask_user", param: str, prompt: str}`
- `TelemetryEvent`: stage ∈ {received, intents_eligible, intent_classified, plan_created,
  plan_communicated, policy_check, tool_execute, respond}; payload is structured.
  - Unknown intent: `intent_classified.payload` includes `{intent_id: null, unknown_intent: true}`.
  - Fallback respond: `respond.payload` includes `{fallback: true, unknown_intent: true}`.

## Telemetry Event Schema & Examples
Schema (logical fields; `PrintSink` omits `timestamp` in stdout but it exists on the event):

```
TelemetryEvent = {
  timestamp: str,              # ISO8601 when available (may be blank in M1)
  interaction_id: str,         # Unique id per interaction/message
  session_id: str,             # Conversation/session identifier
  stage: 'received' | 'intents_eligible' | 'intent_classified' |
         'plan_created' | 'plan_communicated' | 'policy_check' |
         'tool_execute' | 'respond',
  level: 'info' | 'warn' | 'error',
  payload: object              # Structured data, varies by stage
}
```

Payload by stage (M1.1):
- `received`: `{ memory: { history_count: int, params_keys: string[], waiting_for_param: string|null } }`
- `intents_eligible`: `{ eligible: string[] }`
- `intent_classified`:
  - Success: `{ intent_id: string, redacted_params: string[] }`
  - Unknown: `{ intent_id: null, unknown_intent: true }`
- `plan_created`: `{ intent_id: string, steps: string[] }` where step ∈ `['respond','tool_call','ask_user']`
- `plan_communicated`: `{ message: string }` (pre message)
- `policy_check`: `{ allowed: boolean }`
- `tool_execute`: `{ ok: boolean, tool: string }`
- `respond`:
  - Normal: `{ message: string }`
  - AskUser: `{ message: string, waiting_for_param: string }`
  - Fallback/unknown: `{ message: string, fallback: true, unknown_intent: true }`

Examples (as printed by `PrintSink`):

```
{'interaction_id': 'msg-1760559239521',
 'level': 'info',
 'payload': {'memory': {'history_count': 1,
                        'params_keys': [],
                        'waiting_for_param': None}},
 'session_id': 'ui-6f85ba29',
 'stage': 'received'}

{'interaction_id': 'msg-1760559239521',
 'level': 'info',
 'payload': {'eligible': ['order_status']},
 'session_id': 'ui-6f85ba29',
 'stage': 'intents_eligible'}

{'interaction_id': 'msg-1760559255229',
 'level': 'info',
 'payload': {'memory': {'history_count': 2,
                        'params_keys': [],
                        'waiting_for_param': None}},
 'session_id': 'ui-6f85ba29',
 'stage': 'received'}

{'interaction_id': 'msg-1760559255229',
 'level': 'info',
 'payload': {'eligible': ['order_status']},
 'session_id': 'ui-6f85ba29',
 'stage': 'intents_eligible'}
```

Note: For readability, `PrintSink` excludes the raw `timestamp` when printing, but events still include it; structured sinks (e.g., SQLite) should store the full event.
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
  - M1.1: integrated `ConversationMemory` to load/append/clear; includes memory details in telemetry.
  - AskUser flow: when planner emits `AskUser`, Router sets `memory.waiting(param)` and returns the prompt as the response. On subsequent messages, if the waiting `param` is provided (via classifier extraction), Router clears waiting and proceeds to plan/execute.
- Evaluation: Telemetry provides a trace for deterministic evals; later, an `SQLiteSink` will persist events for dashboards and harness.

## Risks & Mitigations
- LLM variability: Enforce JSON response format; validate/guard output; add retries/backoff.
- Parameter collection loops: Use `AskUser` with explicit missing parameter names; persist state in memory; cap clarification turns; provide safe fallback.
- Privacy/PII: Redact sensitive parameters in telemetry per `config/intents.yaml` redaction rules.
- Tool errors: Standardize `ToolResult` with `ok|error`; map errors to friendly copy.
- Coupling creep: Keep router thin; push business logic to adapters/tools.

## Milestones
- M1 (current): Single ToolCall path with pre/post respond; basic telemetry; allow-all policy.
- M1.1 (next):
  - Wire `ConversationMemory` Protocol + `InMemoryConversationMemory` into router.
  - `AskUser` support in planner + router; waiting_user status and resume flow.
  - PlanRunner: per-step status + timestamps; per-step telemetry payloads.
  - Telemetry polish: timestamps; redaction; include `intent_id` across events.
  - Unknown-intent flow: LLM-generated clarification with explicit human-escalation offer; deterministic fallback.
- M2: Expand tools (refund, create_ticket, escalate) and intents; enrich data fixtures.
- M3: YAMLPolicyEngine; enforce policies with composable conditions; log violations.
- M4: Evaluation harness + SQLite sink; golden YAML; CLI `scripts/run_eval.py`.

## Open Questions
- Multi-step plans: Should we allow multiple ToolCalls per plan in M1 or defer?
- Streaming: Do we stream pre/post messages to the UI or return as a single response?
- Memory scope: In-memory only for M1 or add optional SQLite-backed memory?
- Model selection: Per-intent/per-step models vs per-agent default (currently per-agent parameter).
- Error taxonomy: Standardize error codes for tools/policies for easier eval and UI mapping.
 - Fallback customization: Consider a `FallbackResponder` interface and/or config-driven prompts to customize unknown-intent copy without code changes.

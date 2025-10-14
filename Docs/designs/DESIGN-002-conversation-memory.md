# DESIGN-002: Conversation Memory

## Summary
Conversation Memory stores per-session context so the agent can understand multi-turn conversations, reuse previously provided parameters, and resume plans that are waiting on user input. Milestone 1 uses an in-memory store; later milestones persist to SQLite and add summarization.

## Goals
- Maintain per-session history and state (messages, known parameters, waiting prompts).
- Provide compact context to the classifier/planner without exceeding token budgets.
- Enable “ask user” flows and simple plan resumption.

## Non-Goals
- Long-horizon summarization/vector search (later milestone).
- Cross-session identity stitching or PII enrichment.

## Data Model
- Message: `{ role: 'user'|'agent'|'tool', text: str, timestamp: str, metadata: dict }`
- SessionState: `{ session_id: str, history: [Message], params: dict, last_intent_id: str|None, waiting_for_param: str|None, last_result: dict|None, plan_execution?: PlanExecution }`
- Keys come from `interaction.context.session_id` (fallback to `interaction.id`).

## Interfaces
  - `ConversationMemory.for_session(session_id) -> SessionHandle`
  - `SessionHandle` methods:
    - `history() -> list[Message]`, `append(message: Message) -> None`
    - `params() -> dict`, `merge(params: dict) -> None`
    - `waiting() -> str | None`, `set_waiting(name: str | None) -> None`
    - `clear() -> None`, `prune(max_messages: int = 10) -> None`
- `InMemoryConversationMemory` (M1 implementation): dict-backed store with basic pruning; returns lightweight session handles.

## Algorithm (M1)
- On receive: load `{history, params, waiting_for_param}`; prune to last N messages for prompts.
- If `waiting_for_param` is set and the message likely provides it, merge into `params` and clear waiting.
- Classifier/Planner use both current text and `params` to produce a plan.
- If plan includes `AskUser(param, prompt)`: set `waiting_for_param=param`, append the agent prompt, and return.
- On tool success: append a short tool summary and merge any derived parameters (e.g., remember `order_id`).

## "Waiting For Param" State (Deep Dive)
`waiting_for_param` is a per-session flag that records the single required parameter the agent still needs (e.g., `"order_id"`) to proceed.

- Purpose: Prevents guesswork and enables a clean, resumable ask → answer → continue loop across turns.
- When set: Immediately after the Planner returns `AskUser(param, prompt)`, the Router sends the prompt to the user and sets `waiting_for_param = param`.
- While set: The next user message is interpreted primarily as an attempt to provide this parameter. The classifier uses history and `param_mapping` hints to extract it.
- Clearing rules:
  - Extracted successfully → merge into `params` and clear `waiting_for_param`.
  - User resets session → clear memory (including `waiting_for_param`).
  - Future enhancement: timeout or intent change → clear and re-classify.
- Behavior if not provided: Re-ask with the same (or clarified) prompt; avoid looping by escalating or offering examples after N attempts (future).
- Telemetry: Include `waiting_for_param` (name only) and `params_keys` in `received`/`respond` payloads; never log raw values.
- Security: Treat parameter values as sensitive; redact in logs per `redaction.params`.

Example
1) User: "I want to check my order" → Plan returns `AskUser(param="order_id", prompt="What's your order ID?")` → set `waiting_for_param="order_id"` and return the prompt.
2) User: "It's O-12345" → classifier extracts `order_id`, memory merges into `params`, clears `waiting_for_param`, Planner emits ToolCall → execute → respond.

## Router Integration
- Before classification: `history = memory.get_history(sid)`, `params = memory.get_params(sid)`.
- After classification: `memory.merge_params(sid, extracted_params)`.
- When planning returns `AskUser`: `memory.set_waiting_param(sid, param)` and append prompt.
- After response: append agent message; optionally store `last_result`.

## Telemetry & Redaction
- Add `payload.memory: {history_count, params_keys}` to stages `received` and `respond`.
- Do not log raw parameter values; redact per `config/intents.yaml.redaction.params`.

## Persistence (Later)
- SQLite tables: `sessions(session_id, created_at, updated_at)`, `messages(id, session_id, role, text, ts, metadata)`, `state(session_id, params_json, waiting_for_param, last_intent_id, plan_exec_json)`.
- Migrations via a simple script in `scripts/`.

## Edge Cases
- Unknown session: create empty state on first message.
- Resets: user can request reset → `clear(session_id)`.
- Size limits: evict oldest messages beyond threshold; future: token-aware pruning.
- Concurrency: single-threaded for local dev; later use row locks if persisted.

## Testing
- Unit: merge/append/prune behaviors, waiting param set/clear.
- Integration: multi-turn flow that asks for `order_id` then completes.

## Open Questions
- Token-aware pruning target (e.g., 1.5k tokens)?
- Should we persist plan execution state in M1 or recompute on each turn?
- Do we store tool raw outputs in history or only a summarized form?

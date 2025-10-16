# Design: Streamlit Chat UI

## Summary
A minimal Streamlit chat interface exercises the end-to-end agent orchestration with multi-turn memory. The UI sends user messages to `AgentRouter.handle`, renders agent responses, and persists conversation context via `InMemoryConversationMemory`. This enables rapid manual testing of AskUser flows, parameter carry-over, and tool execution without needing the dashboard.

## Goals
- Validate conversation memory across turns (AskUser → user provides → continue plan).
- Use existing adapters: `OpenAIProvider`, YAML intents, `LocalExecutor`, `NullPolicy`, `PrintSink`.
- Provide resettable, session-scoped chat transcripts backed by the same memory the router uses.
- Keep wiring minimal and isolated to `src/ui/chat.py` with no cross-cutting changes.

## Non-Goals
- Production UI (auth, roles, persistence beyond in-memory).
- Token streaming or advanced rendering of tool results.
- Telemetry visualization inside the UI (tracked as a follow-up enhancement).

## Architecture & Components
- UI framework: Streamlit app at `src/ui/chat.py`.
- Orchestration: `AgentRouter` (see DESIGN-003-agent-router) drives classify → plan → policy → execute → respond.
- Memory: `InMemoryConversationMemory` stores `{history, params, waiting}` per session; the same instance is used by the router and UI.
- Intents: `YAMLIntentsRegistry` loads from `config/intents.yaml`.
- LLM: `OpenAIProvider` (JSON mode) used by `LLMIntentClassifier`.
- Tools: `LocalExecutor` with `check_order_status` bound to `JSONDataSource`.
- Telemetry: `PrintSink` prints structured events to stdout during interactions; no UI surface yet.

## Streamlit Basics (What It Is and How It Works)
- Purpose: Streamlit is a lightweight Python framework for building interactive web apps with pure Python. You write a script; Streamlit runs it as a web app.
- Execution model: The script runs top-to-bottom on every user interaction (e.g., a button click). Widgets return values synchronously; Streamlit diffs the UI and updates the browser.
- Sessions: Each browser tab has an independent “session”. Streamlit provides `st.session_state` (a dict) to persist state across reruns for that session.
- Caching: `@st.cache_resource` and `@st.cache_data` persist objects/results across reruns (and across sessions if configured) to avoid expensive re-creation (e.g., model clients, DB connections).
- UI primitives used here:
  - `st.chat_input()` to capture a chat message from the user.
  - `st.chat_message(role)` to render a message bubble for `user` or `agent`.
  - `st.sidebar` for session info and the Reset button.
- Reruns: When the user sends a message, Streamlit reruns the script. We read the transcript from memory and render the full history each time so the UI stays in sync with the authoritative store.
- Limitations (acceptable for our demo): Single-process Python by default, no background jobs, and no built-in auth. It’s great for quick, local instrumentation and prototypes.

### How This App Uses Streamlit
- Session identity: We generate a stable `session_id` with `st.session_state` so the router’s memory can key state per UI session.
- Cached wiring: `@st.cache_resource` holds a single `(router, memory)` instance to avoid re-instantiating adapters on each interaction.
- Stateless function calls, stateful memory: The router is called with an `Interaction`; it updates the in-memory conversation store. The UI simply reads `sesh.history()` and re-renders on each rerun.
- Reset: The sidebar button calls `memory.for_session(sid).clear()` and `st.rerun()` to force a clean transcript for the same session.

### Wiring (Code-Level)
File: `src/ui/chat.py`

```python
@st.cache_resource(show_spinner=False)
def get_router_and_memory():
    ds = JSONDataSource("data/orders.json")
    executor = LocalExecutor()
    executor.register("check_order_status", make_check_order_status(ds))

    policy = NullPolicyEngine()
    telemetry = PrintSink()

    intents = YAMLIntentsRegistry("config/intents.yaml")
    llm = OpenAIProvider(model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini")
    classifier = LLMIntentClassifier(llm)
    planner = SimplePlanner()
    memory = InMemoryConversationMemory(max_messages=20)

    router = AgentRouter(
        intents=intents,
        classifier=classifier,
        planner=planner,
        policy=policy,
        executor=executor,
        telemetry=telemetry,
        memory=memory,
    )
    return router, memory
```

`@st.cache_resource` ensures a single in-process `router` and `memory` instance per Streamlit process (not per message), keeping session state stable across user inputs.

## Data & Schemas
- Reuse existing `TypedDict`s from `src/core/types.py`:
  - `Interaction`: `{id, text, customer_id?, context}`
  - `AgentResponse`: `{text, tool_result?}`
- Data source: `data/orders.json` for order lookups; access via `JSONDataSource`.
- State: Conversation state in `InMemoryConversationMemory` keyed by `session_id`.

## Lifecycle & Flow
1) Ensure `session_id`:
   ```python
   if "session_id" not in st.session_state:
       st.session_state.session_id = f"ui-{uuid.uuid4().hex[:8]}"
   sid = st.session_state.session_id
   ```
2) Render transcript from memory:
   ```python
   sesh = memory.for_session(sid)
   for msg in sesh.history():
       with st.chat_message(msg.get("role", "user")):
           st.write(msg.get("text", ""))
   ```
3) On user input (`st.chat_input`), build an `Interaction` and call the router:
   ```python
   interaction = {"id": f"msg-{int(time.time()*1000)}",
                  "text": prompt,
                  "context": {"session_id": sid, "channel": "chat"}}
   response = router.handle(interaction)
   ```
4) Router internals (see DESIGN-003):
   - Appends user message to memory (`SessionMemoryHandle.append`).
   - Eligible intents → LLM classification → planning.
   - If `AskUser`: sets waiting param, appends agent prompt, returns early.
   - Else: policy check → execute tool → build final text → append agent message.
   - Unknown intent: logs `unknown_intent`, asks the LLM to draft a brief clarification that ALWAYS ends with "Would you like me to loop in a human support agent?", appends it to memory, and returns it (deterministic fallback if LLM fails).
5) UI renders the agent response text and the transcript updates automatically on next render because it reads from the same memory.
6) Reset button calls `memory.for_session(sid).clear()` and triggers `st.rerun()`.

## APIs & Interfaces
- Run: `streamlit run src/ui/chat.py` (or `python -m streamlit run src/ui/chat.py`).
- Environment:
  - `OPENAI_API_KEY` required by `OpenAIProvider`.
  - `OPENAI_MODEL` optional (default `gpt-4o-mini`).
- Public functions in `src/ui/chat.py`:
  - `get_router_and_memory()` (cached): constructs and returns `(router, memory)`.
  - `ensure_session_id() -> str`: returns a UUID-based session id stored in `st.session_state`.
  - `render_sidebar(sid: str, ready: bool)`: shows session info and a Reset button; clears memory for the current session.
  - `main()`: top-level Streamlit entrypoint wiring the chat loop.

## Error Handling & UX
- Missing API key / SDK import errors: caught during router construction; UI shows a clear message and stops.
- Data/intent config issues (bad JSON/YAML): exceptions surface and are shown, prompting a rerun after fixing files.
- Unknown tool: executor returns `{ok: False, error: "unknown_tool"}` and router formats a friendly fallback.
 - Unknown intent: the Router crafts an LLM-backed clarification with an explicit human-escalation offer. The UI simply renders it like any other agent message.

## Policies, Memory, Evaluation
- Policy: `NullPolicyEngine` (allow-all) in M1; future swap to YAML-driven policies requires no UI changes.
- Memory: Session handle façade (`history`, `append`, `params`, `merge`, `waiting`, `set_waiting`, `clear`, `prune`). UI reads history and calls `clear()`; router manages merges and waiting state.
- Evaluation: Not exposed in UI; `PrintSink` emits structured telemetry to stdout which can be inspected during manual runs.

## Security & Redaction
- Telemetry printed to stdout should avoid raw sensitive parameter values; the router already logs only keys for `redacted_params`.
- The UI does not display telemetry yet; when added, mirror redaction rules from `config/intents.yaml.redaction`.

## Performance & Concurrency
- Streamlit runs single Python process with per-user sessions. `@st.cache_resource` ensures we don’t rebuild dependencies on each interaction.
- In-memory store is O(N) in message count per session with simple pruning; default `max_messages=20` in the UI wiring.
- LLM latency dominates response time; acceptable for manual testing.

## Risks & Mitigations
- API dependency flakiness (LLM): surface errors, allow quick reruns; deterministic tests handled in pytest (separate).
- Global resource caching: after config changes, user can rerun app; future enhancement: cache bust on file mtime.
- Memory growth: prune via `max_messages`; future: token-aware pruning.

## Milestones
- M1 (this change): Minimal chat UI with memory and AskUser flows.
- M1.1: Telemetry panel in UI (stages view with redaction, last N events).
- M2: SQLite-backed memory option and session selector.
- M2.1: Stream pre/post messages and tool details in-line.
 - M2.2: Configurable unknown-intent behavior (prompt copy in config and/or pluggable `FallbackResponder`).

## Open Questions
- Should the UI display telemetry events by default or behind a toggle?
- What’s the right default `max_messages` per session for context vs. cost?
- Should we add `customer_id` capture in UI context for richer policies later?

---

References
- Router design: `Docs/designs/DESIGN-003-agent-router.md`
- UI code: `src/ui/chat.py`
- Providers/Adapters: `src/adapters/*`
- Types: `src/core/types.py`

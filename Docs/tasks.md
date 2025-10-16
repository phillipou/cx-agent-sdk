# Active Tasks

Legend: status = todo | in_progress | blocked | review | done

- [in_progress] M1: Core orchestration (LLM intents → plan → respond → tool) — owner @unassigned
  - [done] Create adapters structure and scaffolding
  - [done] Implement `LLMIntentClassifier` (swapped to OpenAI provider)
  - [done] Add `OpenAIProvider` adapter (JSON mode)
  - [done] Remove fake/heuristic classifiers and streamline repo
  - [done] Planner with Respond(pre) → ToolCall → Respond(post)
  - [done] Wire `AgentRouter` E2E with telemetry stages
  - [done] Add ConversationMemory (in-memory) and wire get/append
  - [done] Handle `AskUser` (missing parameters): return clarification and mark waiting
  - [done] Refactor `AgentRouter.handle` into smaller helpers
  - [todo] Add PlanRunner with per-step status (pending → in_progress → completed/failed)
  - [todo] Telemetry polish: timestamps, intent_id, per-step payloads, redaction
  - Links: Docs/designs/DESIGN-001-milestone-1-core-primitives.md, Docs/designs/DESIGN-003-agent-router.md

- [todo] M1: Data fixtures — owner @unassigned
  - [todo] Expand `data/orders.json` (delivered, in_transit, delayed, not_found)
  - [todo] Add a high-level README note on data shapes

- [todo] M1: Deterministic demo and smoke tests — owner @unassigned
  - [todo] Seed minimal pytest in `tests/`
  - [todo] E2E: order found (carrier + ETA)
  - [todo] E2E: order not found (friendly copy)
  - [todo] Unknown intent → clarification
  - [todo] Telemetry sequence + redaction assertions

- [in_progress] M1: Streamlit Chat UI — owner @unassigned
  - [done] Add minimal chat at `src/ui/chat.py` (uses memory)
  - [todo] Sidebar telemetry panel (stages with redaction)
  - [todo] Session selector + reset polish
  - Links: Docs/designs/DESIGN-004-streamlit-chat-ui.md

- [todo] M1.1: Unknown intent experience — owner @unassigned
  - [done] LLM-generated clarification with human-escalation offer
  - [done] Persist fallback messages in memory + telemetry flags
  - [todo] Externalize fallback prompt/copy to config
  - [todo] Consider pluggable `FallbackResponder` interface
  - Links: Docs/designs/DESIGN-003-agent-router.md

# Recently Completed

- [done] Docs scaffolding (templates, ADR-001, DESIGN-001)
- [done] AGENTS.md: docs workflow, intents, comments
- [done] Rename `implementations` → `adapters` and update imports/docs
- [done] Demo script `scripts/run_demo.py` updated to use OpenAI + memory
- [done] Add docstrings/comments across functions (memory, router, adapters, tools)
- [done] Design doc: Agent Router orchestration (DESIGN-003)
- [done] Refactor: `slots` → `params` across code, config, docs
- [done] Repo hygiene: add `.env` and `.gitignore`

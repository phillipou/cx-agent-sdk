# Active Tasks

Legend: status = todo | in_progress | blocked | review | done

- [in_progress] M1: Core orchestration (LLM intents → plan → respond → tool) — owner @unassigned
  - [done] Create adapters structure and scaffolding
  - [done] Implement `LLMIntentClassifier` with fake provider
  - [done] Planner with Respond(pre) → ToolCall → Respond(post)
  - [done] Wire `AgentRouter` E2E with telemetry stages
  - [todo] Add ConversationMemory (in-memory) and wire get/append
  - [todo] Handle `AskUser` (missing parameters): return clarification and mark waiting
  - [todo] Add PlanRunner with per-step status (pending → in_progress → completed/failed)
  - [todo] Telemetry polish: timestamps, intent_id, per-step payloads, redaction
  - Links: Docs/designs/DESIGN-001-milestone-1-core-primitives.md

- [todo] M1: Data fixtures — owner @unassigned
  - [todo] Expand `data/orders.json` (delivered, in_transit, delayed, not_found)
  - [todo] Add a high-level README note on data shapes

- [todo] M1: Deterministic demo and smoke tests — owner @unassigned
  - [todo] Seed minimal pytest in `tests/`
  - [todo] E2E: order found (carrier + ETA)
  - [todo] E2E: order not found (friendly copy)
  - [todo] Unknown intent → clarification
  - [todo] Telemetry sequence + redaction assertions

# Recently Completed

- [done] Docs scaffolding (templates, ADR-001, DESIGN-001)
- [done] AGENTS.md: docs workflow, intents, comments
- [done] Rename `implementations` → `adapters` and update imports/docs
- [done] Demo script `scripts/run_demo.py` (LLM classifier path)
- [done] Add docstrings/comments across functions (memory, router, adapters, tools)

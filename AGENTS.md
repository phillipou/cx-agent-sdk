# Repository Guidelines

## Project Structure & Module Organization
- `Docs/`: Product docs (see `Docs/PRD.md`).
- `Docs/designs/`: Feature-level technical designs (RFCs).
- `Docs/adr/`: Architecture Decision Records (append-only; supersede when needed).
- `Docs/templates/`: Reusable templates for ADRs and designs.
- `config/`: Runtime configs (e.g., `policies.yaml`, `intents.yaml`).
- `src/`: Python source (planned):
  - `src/core/` (protocols: DataSource, LLMProvider, PolicyEngine, ToolExecutor, TelemetrySink)
  - `src/agent/` (AgentRouter, ConversationMemory)
- `src/adapters/`: Concrete adapters for core interfaces
  - `adapters/datasource/` (e.g., `json_data_source.py`)
  - `adapters/policy/` (e.g., `null_policy.py`)
  - `adapters/telemetry/` (e.g., `print_sink.py`)
  - `adapters/executor/` (e.g., `local_executor.py`)
  - `adapters/intents/` (e.g., `yaml_registry.py`)
  - `adapters/classifier/` (`llm_intent_classifier.py`)
  - `adapters/planner/` (`simple_planner.py`)
  - `adapters/llm/` (`openai_provider.py`)
  - `src/tools/` (tool schemas + functions)
- `src/ui/` (Streamlit apps: `chat.py`, `dashboard.py`)
- `config/`: Runtime configs (e.g., `policies.yaml`).
- `scripts/`: CLIs (e.g., `run_eval.py`, `seed_database.py`).
- `data/`: Mock datasets (orders/tickets, SQLite).
- `tests/`: Pytest suites.
  
## Memory Component
- `src/adapters/memory/`: Conversation memory adapters
  - `in_memory.py`: `InMemoryConversationMemory` (Session handle façade)
- Recommended API (M1): `memory.for_session(session_id)` returns a handle:
  - `history()`, `append(message)`, `params()`, `merge(params)`, `waiting()`, `set_waiting(name|None)`, `prune()`, `clear()`.
  - Prefer this façade for readability; swap the backend later (SQLite) without changing Router logic.

## Documentation Workflow
- Source of truth: `Docs/PRD.md`.
- New design: copy `Docs/templates/DESIGN-TEMPLATE.md` → `Docs/designs/DESIGN-<NNN>-<slug>.md`.
- New decision: copy `Docs/templates/ADR-TEMPLATE.md` → `Docs/adr/ADR-<NNN>-<slug>.md`.
- Branch/PR: `docs/<topic>`; title `docs(design|adr): <summary>`; include “Open Questions”.
- Reviews: require PM + Eng sign-off; ADRs are immutable (supersede with a new ADR).
- Intents & planning: define in `config/intents.yaml`; keep parameter extraction rules in config; redact sensitive parameters in telemetry.

## Task Tracking (Docs/tasks.md)
- Location: `Docs/tasks.md` (single Markdown file tracked in git).
- Format: checklist per task with metadata and nested subtasks.
- Status values: `todo | in_progress | blocked | review | done`.
- Workflow:
  - Before starting: add a task with goal, owner, links to PRD/design.
  - During work: break into subtasks, update status daily, link active PRs.
  - After merge: mark `done`, add follow-ups or ADR links if decisions changed.
  - On completion: immediately update `Docs/tasks.md`; move the item (or summarize) to “Recently Completed” with date/PR link.
- Example:
  - [in_progress] M1: LLM intent classification — owner @you
    - [done] Scaffold `src/adapters/...`
    - [in_progress] `LLMIntentClassifier` + Fake provider
    - [todo] Wire `AgentRouter.handle` pre/post respond
    - Links: PR #123, design Docs/designs/DESIGN-001-milestone-1-core-primitives.md

## Build, Test, and Development Commands
- Create env + install: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run deterministic evals: `python scripts/run_eval.py`
- Seed SQLite (when added): `python scripts/seed_database.py`
- Launch chat UI: `streamlit run src/ui/chat.py`
- Launch dashboard: `streamlit run src/ui/dashboard.py`

### LLM Setup
- Set `OPENAI_API_KEY` in your environment.
- Choose models programmatically per agent/function (pass `model=` to `OpenAIProvider`).
  An `OPENAI_MODEL` env var is supported as a fallback but is discouraged.
- The demo uses the OpenAI provider; see `scripts/run_demo.py`.

## Coding Style & Naming Conventions
- Python 3.11+, PEP 8, type hints required. Use docstrings on public APIs.
- Names: modules `snake_case`, classes `PascalCase`, functions/vars `snake_case`.
- Prefer pure functions for tools; separate I/O from logic.
- Formatting/linting (if configured): `black .` and `ruff check .` before PRs.

## Documentation & Comments
- Every function/method: include a concise docstring (1–3 lines) explaining purpose, key inputs/outputs, and notable side effects. For trivial helpers, add a one-line comment at minimum.
- Docstrings: required on public modules/classes/functions; include param/return types and brief examples when helpful.
- Inline comments: be generous—explain the “why” behind non-obvious logic (routing, planning, policy decisions) and reference `Docs/designs/*` or ADR IDs.
- Traceability: when behavior changes, update or link to the relevant design/ADR; add file paths in comments for quick navigation.
- Readability first: avoid clever one-liners; prefer explicit variable names and small, named helpers with comments.
- Telemetry as docs: emit clear stages and reasons; redact sensitive parameters per `config/intents.yaml`.

## Testing Guidelines
- Framework: `pytest` with `tests/` mirroring `src/` layout.
- File names: `test_*.py`; functions: `test_<unit_of_behavior>()`.
- Cover: core primitives, tool happy/edge cases, policy decisions, and evaluation runner.
- Use deterministic fixtures and mock integrations (latency, errors, rate limits).

## Commit & Pull Request Guidelines
- Commits: follow Conventional Commits (e.g., `feat: add refund tool`, `fix: handle 404 from MockShopify`).
- PRs: clear description, linked issue, screenshots for UI, and sample eval output (e.g., SQLite run ID or CLI logs).
- Include notes on policy/config changes (`config/policies.yaml`) and data migrations.
- Keep changes small, focused, and covered by tests.

## Architecture Overview (Agent-Specific)
- Five swappable primitives power the Agent: DataSource, LLMProvider, PolicyEngine, ToolExecutor, TelemetrySink.
- AgentRouter orchestrates: classify → validate (policy) → execute tool → log → respond; supports multi-turn memory.
- Start locally with JSON mocks and OpenAI for classification; swap implementations without touching orchestration.

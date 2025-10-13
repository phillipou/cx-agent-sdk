# **PRD: CX Agent SDK**

**Author:** Phil Ou  
 **Status:** Final  
 **Created:** October 13, 2025

---

## **1\. Overview & Problem Statement**

**What:** A minimal Agent SDK that simulates how customer support agents are built, evaluated, and monitored in production. Think "Sierra's internal SDK" but scoped to focused learning milestones.

**Problem:** Product managers joining Sierra need hands-on understanding of agentic systems — specifically how routing, tool orchestration, policy enforcement, and evaluation work in practice. Reading docs isn't enough; you need to build the primitives yourself to understand trade-offs.

**Why this matters:** Without touching the internals, PMs can't make informed decisions about:

* When to route to humans vs auto-resolve  
* How policies constrain agent behavior  
* What metrics actually indicate agent quality  
* Why certain architectures scale better than others

---

## **2\. Goals**

### **In Scope**

1. **Build a working agent** that handles customer support interactions with multi-turn conversations and memory  
2. **Implement 5 core primitives** (DataSource, LLMProvider, PolicyEngine, ToolExecutor, TelemetrySink) with swappable implementations  
3. **Create mock integrations** that simulate real external systems (Shopify-like order APIs, Zendesk-like ticketing)  
4. **Create an evaluation harness** that runs golden test cases with both deterministic and LLM-as-judge evaluation  
5. **Build interfaces** (dashboard for results visualization, chat UI for live testing)  
6. **Document architecture decisions** (ADRs) explaining why each primitive exists and what it abstracts

### **Out of Scope**

* Production deployment (local-only, no auth, no rate limiting, no infrastructure)

### **Success Criteria**

* Agent resolves 12/15 golden test cases correctly (deterministic eval)  
* LLM-as-judge scores agent responses ≥80% on semantic correctness  
* Multi-turn conversations maintain context across 3+ exchanges  
* Can swap LLM provider (OpenAI → Anthropic) in \<5 lines of code  
* Can swap data source (JSON → SQLite → Mock API) without changing AgentRouter  
* Policy engine supports arbitrary rule complexity (composable conditions)  
* Codebase has 3+ ADRs explaining key design decisions

---

## **3\. Requirements**

### **3.1 Functional Requirements**

**Agent Capabilities**

* FR1: Accept customer interaction as input (JSON: `{id, text, customer_id, context: {...}}`)  
* FR2: Classify intent and route to appropriate tool  
* FR3: Execute tool with validated parameters  
* FR4: Return resolution, create/update tickets, or escalate to human with reason  
* FR5: Enforce policies before tool execution (e.g., refund caps, order age limits)  
* FR6: Maintain conversation memory across multiple turns  
* FR7: Reference previous exchanges and build on context

**Interaction Types**

* FR8: Handle live customer messages (chat-based support)  
* FR9: Create tickets from interactions when needed (agent decides based on complexity/async nature)  
* FR10: Update existing ticket status/metadata  
* FR11: Retrieve and reference ticket history when relevant

**Tool Palette** (minimum 4 tools)

* FR12: `check_order_status(order_id)` → returns shipping/delivery info (structured data)  
* FR13: `issue_refund(order_id, amount, reason)` → processes refund with policy checks  
* FR14: `create_ticket(customer_id, issue_type, description)` → creates ticket for async follow-up  
* FR15: `escalate_to_human(interaction_id, reason, context)` → flags for human review  
* FR16: Tools return structured data and handle errors (order not found, refund already issued, etc.)

**Mock Integrations**

* FR17: Simulate Shopify-like order management API (CRUD operations on orders)  
* FR18: Simulate Zendesk-like ticketing system (create, update, search tickets)  
* FR19: Mock integrations include realistic latency, rate limits, and error responses  
* FR20: Support swapping mock → real API without changing tool implementations

**Policy System**

* FR21: Load policies from YAML config (`config/policies.yaml`)  
* FR22: Support arbitrary rule complexity with composable conditions (e.g., `if customer.tier == 'VIP' and amount < 1000: allow`)  
* FR23: Validate tool calls against rules (refund thresholds, order age, customer tier, etc.)  
* FR24: Block disallowed actions and log violations with severity  
* FR25: Support policy updates without code changes

**Memory & Context Management**

* FR26: Store conversation history per session  
* FR27: Retrieve relevant context for each new message  
* FR28: Support clearing/resetting conversation memory  
* FR29: Include conversation context in policy decisions (e.g., "user already asked twice")

**Evaluation**

* FR30: Load golden test set (YAML file with interactions \+ expected outcomes)  
* FR31: Support both single-shot and multi-turn test scenarios  
* FR32: Run agent on all test cases  
* FR33: **Deterministic eval:** Compare actual vs expected (tool name \+ params within acceptable range)  
* FR34: **LLM-as-judge eval:** Use GPT-4 to score semantic correctness of resolutions  
* FR35: Calculate containment rate (% resolved without escalation)  
* FR36: Log results to persistent storage (SQLite) with both eval scores

**Dashboard**

* FR37: Display eval results table (interaction → action → deterministic pass/fail → LLM judge score)  
* FR38: Show containment rate visualization  
* FR39: Drill into individual interaction traces (step-by-step: LLM → policy → tool → result)  
* FR40: View conversation history for multi-turn scenarios

**Chat Interface**

* FR41: Streamlit chat UI for live agent testing  
* FR42: Send messages and see agent responses in real-time  
* FR43: View tool calls and policy decisions inline  
* FR44: Display conversation memory/context  
* FR45: Support session reset

**Intents & Planning**

* FR46: Define eligible intents in `config/intents.yaml` (id, description, required slots, tool mapping, constraints)  
* FR47: Determine eligible intents per interaction based on context (channel, rollout, customer tier)  
* FR48: Classify the user message to a supported intent (or none) using LLM or heuristics  
* FR49: Extract required slots (e.g., `order_id`) from text or history; prompt user when missing  
* FR50: Produce a plan (one or more steps) from the selected intent; M1 supports a single tool step  
* FR51: Support `ask_user` planning step for missing slots, to be expanded in later milestones  
* FR52: Expose intent and plan in telemetry and UIs (trace view)  
* FR53: Unknown/disabled intents result in safe fallback (clarify, create ticket, or escalate)

### **3.2 Design Principles**

**Composability**

* Each primitive (DataSource, LLMProvider, PolicyEngine, ToolExecutor, TelemetrySink) is independently swappable  
* Adding a new tool is straightforward (define schema \+ implementation)  
* Clear separation: `/core` (protocols), `/implementations` (concrete classes), `/agent` (orchestration)

**Policy Flexibility**

* Policy engine supports composable rules (AND, OR, NOT conditions)  
* Rules can reference customer context, order data, interaction metadata, conversation history  
* Easy to add new rule types without changing engine code

**Performance**

* Agent responds in a timely manner (single-digit seconds for resolution)  
* Dashboard loads quickly and remains responsive  
* Eval harness completes test suite without blocking

**Observability**

* Every agent invocation is traceable (what happened, why, when)  
* Policy violations are logged with context  
* Results are queryable (by date, interaction ID, tool, outcome)  
* Conversation traces show full multi-turn context

**Usability**

* CLI command to run eval: `python scripts/run_eval.py`  
* Streamlit UIs launch with single command  
* README has clear quickstart (setup → run → interpret results)

### **3.3 Technical Constraints**

**Stack**

* Python 3.11+  
* OpenAI API for LLM (native function calling)  
* SQLite for data persistence  
* Streamlit for UI  
* PyYAML for config  
* No heavy frameworks (LangChain, LlamaIndex) — build orchestration from scratch

**Data**

* Mock orders dataset (JSON/SQLite) with 20-30 synthetic orders  
* Orders cover edge cases (old orders, high-value, missing IDs)  
* Golden test set (YAML) with single-shot and multi-turn scenarios  
* Mock API responses for integration simulation
* Intents configuration file `config/intents.yaml` checked into source control

---

## **4\. Milestones**

### **Milestone 1: Core Primitives & Basic Agent**

**Goal:** Get a single interaction resolved end-to-end through all 5 primitives

**Deliverables:**

* Define 5 protocol interfaces in `/core` (DataSource, LLMProvider, PolicyEngine, ToolExecutor, TelemetrySink)  
* Implement minimum viable versions:  
  * `JSONDataSource` (reads mock orders)  
  * `OpenAIProvider` (calls OpenAI API with function calling)  
  * `NullPolicyEngine` (allows everything, logs nothing — just a passthrough)  
  * `LocalExecutor` (executes Python functions directly)  
  * `PrintSink` (prints events to console)  
* Wire `AgentRouter` that orchestrates all primitives and intents/planning  
* Create 1 tool: `check_order_status(order_id)`  
* Add intents: `config/intents.yaml` with `order_status` intent (slots: `order_id`)  
* Add simple `IntentClassifier`/`Planner` (heuristic/regex) that produces a single-step plan  
* Test: Agent receives "Where's my order O-12345?" → calls tool → returns status

**Success:** One interaction flows through: input → LLM → tool execution → output

---

### **Milestone 2: Tool Suite & Mock Data**

**Goal:** Build complete tool palette with realistic mock data

**Deliverables:**

* Create mock orders dataset (20-30 orders in JSON) covering:  
  * Normal orders (shipped, delivered)  
  * Edge cases (old orders, high-value, missing IDs, already refunded)  
  * Different customer tiers (standard, VIP)  
* Implement 4 tools with structured responses:  
  * `check_order_status(order_id)`  
  * `issue_refund(order_id, amount, reason)`  
  * `create_ticket(customer_id, issue_type, description)`  
  * `escalate_to_human(interaction_id, reason, context)`  
* Add error handling (order not found, invalid state transitions)  
* Expand intents and planning:  
  * `refund_request` (slots: `order_id`, `amount`, `reason`) → plan may include `ask_user` for missing slots  
  * `create_ticket_intent` (slots: `issue_type`, `description`)  
  * Update classifier to choose among multiple intents and slot fill from history  
* Test each tool in isolation with mock data

**Success:** All 4 tools work with realistic mock data and handle errors gracefully

---

### **Milestone 3: Policy Engine**

**Goal:** Implement composable policy validation that blocks disallowed actions

**Deliverables:**

* Design `YAMLPolicyEngine` that reads `config/policies.yaml`  
* Support composable conditions (AND, OR, NOT, threshold comparisons)  
* Implement 5 sample policies:  
  * Refund auto-approve threshold ($50)  
  * Maximum refund amount ($500)  
  * Order age requirement (within 30 days)  
  * VIP customer override (higher limits)  
  * Escalation triggers (angry sentiment, policy violations)  
* Replace `NullPolicyEngine` with `YAMLPolicyEngine` in AgentRouter  
* Add policy violation logging to telemetry  
* Test: Agent blocks out-of-policy refund, logs violation, escalates

**Success:** Agent enforces policies, blocks disallowed actions, logs violations with context

---

### **Milestone 4: Evaluation Harness (Deterministic)**

**Goal:** Run golden test set with deterministic pass/fail criteria

**Deliverables:**

* Create golden test set (15 single-shot interactions in YAML) with expected outcomes:  
  * Tool name  
  * Parameter ranges (e.g., refund amount ±$5)  
  * Expected escalations  
* Build `EvaluationRunner` that:  
  * Loads test set  
  * Runs agent on each interaction  
  * Compares actual vs expected (intent, plan steps, tool \+ params)  
  * Calculates pass/fail, containment rate  
* Implement `SQLiteSink` to replace `PrintSink`  
* Log all eval results to database  
* CLI script: `python scripts/run_eval.py`

**Success:** Eval runs 15 tests, logs results to SQLite, calculates containment rate (target: 80%+)

---

### **Milestone 5: LLM-as-Judge Evaluation**

**Goal:** Add semantic evaluation for resolution quality

**Deliverables:**

* Build `LLMJudge` class that:  
  * Takes interaction \+ agent response  
  * Prompts GPT-4 to score (0-10) on: correctness, tone, completeness  
  * Returns structured score \+ reasoning  
* Update eval harness to run both deterministic \+ LLM judge  
* Store both scores in SQLite  
* Update golden test set with semantic correctness criteria  
* Generate eval report showing:  
  * Deterministic pass rate  
  * Average LLM judge score  
  * Per-test breakdown

**Success:** Eval includes both deterministic (80%+ pass) and semantic (8+/10 avg score) metrics

---

### **Milestone 6: Multi-Turn Conversations & Memory**

**Goal:** Enable agent to handle conversations with context across multiple exchanges

**Deliverables:**

* Implement `ConversationMemory` component:  
  * Store message history per session  
  * Retrieve relevant context for new messages  
  * Support memory reset  
* Update `AgentRouter` to include conversation history in LLM calls  
* Add memory-aware policy rules (e.g., escalate if user repeats question)  
* Create 5 multi-turn test scenarios in golden set:  
  * User asks for order status, then requests refund  
  * User provides incomplete info, agent asks follow-up, user responds  
  * User changes request mid-conversation  
* Update eval harness to support multi-turn scenarios  
* Test: 3+ turn conversation maintains context

**Success:** Agent handles multi-turn conversations, references previous exchanges appropriately

---

### **Milestone 7: Mock Integrations**

**Goal:** Simulate real external systems (Shopify, Zendesk) with realistic behavior

**Deliverables:**

* Build `MockShopifyAPI` class:  
  * CRUD operations on orders  
  * Simulated latency (100-500ms)  
  * Rate limiting (10 req/sec)  
  * Error responses (404, 429, 500\)  
* Build `MockZendeskAPI` class:  
  * Create, update, search tickets  
  * Simulated latency  
  * Realistic ticket lifecycle  
* Create `APIDataSource` that wraps mock APIs  
* Update tools to use API data source instead of direct JSON  
* Test: Agent works with API-based data source, handles errors

**Success:** Can swap JSON → SQLite → Mock API without changing AgentRouter

---

### **Milestone 8: Multiple Data Sources**

**Goal:** Prove DataSource abstraction works across implementations

**Deliverables:**

* Implement `SQLiteDataSource` (migrate mock orders to SQLite)  
* Add seed script: `python scripts/seed_database.py`  
* Test AgentRouter with JSON, SQLite, and Mock API sources  
* Update README with instructions for switching data sources  
* Write ADR explaining DataSource abstraction design

**Success:** Can swap data sources in \<5 lines, agent works identically with all three

---

### **Milestone 9: Chat Interface**

**Goal:** Live agent testing with visible tool calls and memory

**Deliverables:**

* Streamlit chat UI with message input  
* Real-time agent responses  
* Inline display of intent selection, plan steps, tool calls, policy decisions, reasoning  
* Conversation memory display (show history)  
* Session reset button  
* Launch: `streamlit run src/ui/chat.py`

**Success:** Can chat with agent, maintain multi-turn context, see full decision trace inline

---

### **Milestone 10: Dashboard**

**Goal:** Visualize eval results and interaction traces

**Deliverables:**

* Streamlit app reading from SQLite  
* Results table (sortable, filterable)  
* Containment rate chart over time  
* Individual interaction trace viewer (LLM → policy → tool → result)  
* Multi-turn conversation viewer  
* Launch: `streamlit run src/ui/dashboard.py`

**Success:** Dashboard loads \<2 seconds, shows all eval results with drill-down capability

---

### **Milestone 11: Documentation & Polish**

**Goal:** Make project portfolio-ready

**Deliverables:**

* Write 5+ ADRs:  
  * ADR-001: Why these 5 primitives  
  * ADR-002: Policy engine design (composable rules)  
  * ADR-003: Hybrid evaluation approach  
  * ADR-004: Memory/context management design  
  * ADR-005: Mock integration architecture  
* README with:  
  * Quickstart (setup → run → interpret)  
  * Architecture overview  
**Intent-Driven Planning**

* Constrain behavior via an explicit intents registry loaded from config  
* Separate concerns: intent eligibility → classification → planning → policy → execution  
* Slot filling is explicit; user prompts occur only when required data is missing  
* Intents and plans are inspectable and logged for evaluation
  * Adding new tools guide  
  * Swapping primitives guide  
  * Multi-turn conversation design  
* Code cleanup: docstrings, type hints, comments  
* Example outputs in `/docs` (sample eval run, trace screenshots, multi-turn examples)

**Success:** Someone unfamiliar can clone, setup, and run eval in \<15 minutes

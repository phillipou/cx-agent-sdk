# DESIGN-001: Milestone 1 – Core Primitives & Multi-Turn Agent

## Summary
Build a minimal agent that resolves customer support interactions using LLM-based classification and planning. Support multi-turn conversations where the agent can ask follow-up questions to collect missing information.

## Goals
- Multi-turn conversation support (agent asks for missing info, user responds)
- LLM-driven decision making (OpenAI for classification and planning, abstracted via LLMProvider)
- Swappable primitives (6 core interfaces)
- Full observability (telemetry at each stage)

## Non-Goals
- Production deployment, auth, real APIs
- Advanced conversation management (summarization, context window optimization)
- Complex multi-step plans (M1: single action per turn)

---

## Architecture & Components

### The 6 Core Primitives

**AgentRouter** - Orchestrates all components, manages conversation flow

**1. ConversationMemory** - Store message history per session
- `get_history(session_id) -> list[Message]`
- `append(session_id, message) -> None`
- `clear(session_id) -> None`
- M1: `InMemoryConversationMemory` (simple dict)

**2. DataSource** - Fetch customer/order data
- `get_order(order_id) -> dict | None`
- `get_customer(customer_id) -> dict | None`
- M1: `JSONDataSource` reads from `data/orders.json`

**3. LLMProvider** - Abstract LLM API calls (enables swapping providers)
- `generate(messages, tools, response_format, temperature) -> LLMResponse`
- `get_cost(tokens_in, tokens_out) -> float`
- M1: `OpenAIProvider` (GPT-4)
- M2+: Can swap to `AnthropicProvider`, `LocalModelProvider`, etc.

**4. PolicyEngine** - Validate actions before execution
- `validate(plan, interaction, history) -> PolicyDecision`
- M1: `NullPolicyEngine` always returns `allowed=True`

**5. ToolExecutor** - Execute tools (check order, issue refund, etc.)
- `execute(tool_call, context) -> ToolResult`
- M1: `LocalExecutor` with registered tool handlers

**6. TelemetrySink** - Log events
- `record(event) -> None`
- M1: `PrintSink` logs to stdout
- M4: `SQLiteSink`

### Supporting Components

**IntentsRegistry** - Define available intents
- `get_eligible(context) -> list[Intent]`
- Loads from `config/intents.yaml`
- Filters by channel, rollout %, customer tier

**IntentClassifier** - LLM-based intent classification
- `classify(interaction, intents, history) -> ClassificationResult`
- Uses `LLMProvider` to determine what user wants
- Extracts intent parameters (order_id, amount, etc.)
- Returns missing parameters

**Planner** - LLM-based execution planning
- `plan(classification, interaction, history) -> Plan`
- Uses `LLMProvider` for function calling or prompt generation
- If parameters complete: generates `ToolCall`
- If parameters missing: generates `AskUser` with prompt

---

## Key Types

### Core Data Structures
```python
Message = {role: 'user'|'agent', text: str, timestamp: str, metadata: dict}

Interaction = {id: str, text: str, customer_id: str|None, context: dict}

Intent = {
    id: str,
    description: str,
    required_params: list[str],
    tool: str,
    constraints: {channels: list, rollout: int, min_tier: str}
}

IntentContext = {channel: str, customer_id: str|None, customer_tier: str|None}
```

### LLM Types
```python
LLMResponse = {
    content: str | None,           # Text response
    tool_calls: list[ToolCall],    # Function calls (if tools provided)
    model: str,
    tokens_used: int,
    latency_ms: int
}
```

### Classification & Planning
```python
ClassificationResult = {
    intent: Intent | None,
    extracted_params: dict,       # Found in current message
    missing_params: list[str],    # Still needed
    confidence: float
}

ToolCall = {tool_name: str, params: dict}

AskUser = {param: str, prompt: str}
Respond = {when: 'pre'|'post'|'error', message: str}

Plan = {
    intent_id: str,
    steps: list[ToolCall | AskUser | Respond],  # M1: typically Respond(pre) -> ToolCall -> Respond(post)
    reasoning: str
}
```

### Results
```python
PolicyDecision = {
    allowed: bool,
    violations: list[str],
    requires_escalation: bool
}

ToolResult = {
    success: bool,
    data: dict | None,
    error: str | None,
    execution_time_ms: int
}

AgentResponse = {
    text: str,
    tool_result: ToolResult | None,
    needs_user_input: bool,
    missing_param: str | None
}
```

---

## End-to-End Flow

### AgentRouter.resolve(interaction, session_id) Flow

1. **Load history** from `ConversationMemory`
2. **Get eligible intents** from `IntentsRegistry` (filtered by context)
3. **Classify intent** using `IntentClassifier` (calls `LLMProvider`)
   - Returns: intent, extracted_params, missing_params, confidence
4. **Generate plan** using `Planner` (calls `LLMProvider`)
   - If parameters missing: `AskUser`
   - If parameters complete: include `Respond(pre)` then `ToolCall`; planner drafts `Respond(post)` template to summarize the result
5. **Validate** with `PolicyEngine` (M1: always allows)
6. **Communicate plan**: send `Respond(pre)` to the user ("I’ll check your order now…")
7. **Execute**:
   - If `ToolCall`: validate with `PolicyEngine`, then execute via `ToolExecutor`
   - If `AskUser`: skip execution and await user reply
8. **Format response**: build final message using `Respond(post)` with tool result
8. **Store messages** in `ConversationMemory`
9. **Log telemetry** at each stage via `TelemetrySink` (see Telemetry section)

### Example: Single-Turn (Complete Information)
```
User: "Where's my order O-12345?"

1. Load history: []
2. Eligible intents: [order_status]
3. Classify: intent=order_status, params={order_id: "O-12345"}, missing=[]
4. Plan: [Respond(pre:"I’ll check order O-12345."), ToolCall(check_order_status,{order_id}), Respond(post:"Summary…")]
5. Communicate plan: send pre-respond
6. Validate: allowed=True
7. Execute: fetch order from DataSource
8. Format: "Your order O-12345 is shipped via UPS, ETA Oct 20"
9. Store: user message + agent response
10. Log: all stages

Response: "Your order O-12345 is shipped via UPS, ETA Oct 20"
```

### Example: Multi-Turn (Missing Information)
```
Turn 1:
User: "I want to check my order"

1. Classify: intent=order_status, params={}, missing=[order_id]
2. Plan: AskUser(param="order_id", prompt="What's your order ID?")
3. Skip execution
4. Return: "What's your order ID?"
5. Store in memory

---

Turn 2:
User: "O-12345"

1. Load history: [{user: "check my order"}, {agent: "What's your order ID?"}]
3. Classify (with context): intent=order_status, params={order_id: "O-12345"}
4. Plan: ToolCall(check_order_status, {order_id: "O-12345"})
5. Communicate plan: Respond(pre)
6. Execute: fetch order
7. Format: Respond(post): "Your order O-12345 is shipped..."
```

---

## Plan Execution & State

Track each plan step for clarity, retries, and resumability (in-memory in M1; persist later).

- StepStatus: `pending | in_progress | completed | failed | blocked | waiting_user | canceled`.
- PlanExecution: `{ plan_id, intent_id, steps: [{step, status, started_at?, ended_at?, error?}], current_index }`.
- Algorithm:
  1) Pre-Respond: status `in_progress` → send → `completed` (telemetry: plan_communicated).
  2) ToolCall: `policy_check` → on allow execute and mark `completed`; on deny/error mark `failed` and add `Respond(error)`.
  3) Post-Respond: summarize result → `completed`.
  4) AskUser: mark `waiting_user`, return early; resume on next message at `current_index`.
- Idempotency: compute `idempotency_key` per ToolCall (intent+params); executor can short-circuit duplicates (M2+).
- Retries: none in M1; add backoff for transient errors later.

---

## Telemetry

Emit structured events at each stage to enable debugging and evaluation. Redact sensitive parameters per config.

Stages: `received`, `intents_eligible`, `intent_classified`, `plan_created`, `plan_communicated`, `policy_check`, `tool_execute`, `respond`.

Payload fields (examples): `{ intent_id, step_index, step_type, status, params_redacted: true, redacted_params: [...], durations_ms, error_code }`.

Mask parameter values defined under `redaction.params` in `config/intents.yaml`.

---

## LLM Integration

### IntentClassifier uses LLMProvider

**Calls:** `llm.generate(messages, response_format={json_schema})`

**Prompt includes:**
- Conversation history
- Available intents with descriptions
- Current message

**Returns:** Structured JSON with intent_id, extracted_params, missing_params, confidence

### Planner uses LLMProvider

**If parameters missing:**
- Calls: `llm.generate(messages)` to generate natural question
- Returns: `AskUser`

**If parameters complete:**
- Calls: `llm.generate(messages, tools={tool_schemas})` with function calling
- Returns: `ToolCall`

---

## Configuration

### Intents Config (`config/intents.yaml`)
```yaml
intents:
  - id: order_status
    description: Retrieve shipping/delivery info for a given order
    required_params: [order_id]
    tool: check_order_status
    constraints:
      channels: [chat]
      rollout: 100
      min_tier: null
```

### Orders Data (`data/orders.json`)
```json
{
  "O-12345": {
    "order_id": "O-12345",
    "customer_id": "C-001",
    "status": "shipped",
    "carrier": "UPS",
    "tracking": "1Z999...",
    "eta": "2025-10-20",
    "amount": 29.99,
    "items": ["Blue T-Shirt (M)"]
  }
}
```

Include orders with: shipped, delivered, in_transit, delayed, not_found, refunded states.

---

## Telemetry Stages

Every interaction logs these stages in order:

1. `received` - Interaction received
2. `history_loaded` - Conversation history retrieved (count)
3. `intents_eligible` - Eligible intents determined (list)
4. `intent_classified` - Intent + parameters extracted (intent_id, confidence, params)
5. `plan_created` - ToolCall or AskUser generated
6. `plan_type` - Type: 'tool_call' or 'ask_user'
7. `policy_check` - Policy validation result (allowed, violations)
8. `tool_execute` - Tool execution (only if ToolCall: tool_name, success, time)
9. `response_generated` - Final response formatted (length, needs_input)
10. `memory_updated` - History stored (total message count)

Each event includes: `timestamp`, `session_id`, `interaction_id`, `stage`, `level`, `payload`

---

## Error Handling

**No intent matched:**
- Return: "I'm not sure how to help with that. Could you rephrase?"

**Order not found:**
- ToolResult with success=False, error="Order {order_id} not found"
- Format: "Sorry, I couldn't find order {order_id}"

**Policy violation (M3+):**
- Return: "I can't process that request: {violation_reason}"

**LLM error (timeout, rate limit):**
- Log to telemetry with level=error
- Return: "Something went wrong. Please try again."

---

## Testing Plan

### Unit Tests
- Tool behavior (happy path, order not found)
- DataSource lookups (valid/invalid order_id)
- IntentsRegistry filtering (channel, rollout, tier)
- LLMProvider response parsing

### Integration Tests

**Test 1: Single-turn with complete info**
```python
response = router.resolve(
    Interaction(text="Where's order O-12345?"),
    session_id="test-1"
)
assert "shipped" in response.text.lower()
assert response.needs_user_input == False
```

**Test 2: Multi-turn with parameter collection**
```python
# Turn 1
response1 = router.resolve(
    Interaction(text="Check my order"),
    session_id="test-2"
)
assert response1.needs_user_input == True
assert "order ID" in response1.text.lower()

# Turn 2
response2 = router.resolve(
    Interaction(text="O-12345"),
    session_id="test-2"
)
assert "shipped" in response2.text.lower()
```

**Test 3: Telemetry stages**
```python
events = []
router = AgentRouter(..., telemetry=MockSink(events))
router.resolve(Interaction(text="Where's O-12345?"), "test-3")

stages = [e.stage for e in events]
assert stages == [
    'received', 'history_loaded', 'intents_eligible',
    'intent_classified', 'plan_created', 'plan_type',
    'policy_check', 'tool_execute', 'response_generated',
    'memory_updated'
]
```

**Test 4: LLM Provider swappability**
```python
# M1: OpenAI
router1 = AgentRouter(llm_provider=OpenAIProvider(...), ...)

# M2: Anthropic (same interface)
router2 = AgentRouter(llm_provider=AnthropicProvider(...), ...)

# Both work identically
```

---

## Tool Registration

Tools are registered at `ToolExecutor` initialization:

```python
class LocalExecutor:
    def __init__(self, data_source: DataSource):
        self.data_source = data_source
        self.tools = {
            "check_order_status": self._check_order_status
        }
    
    def _check_order_status(self, order_id: str) -> ToolResult:
        # Implementation uses self.data_source
```

Adding new tools: define handler function, add to registry dict.

---

## M1 Acceptance Criteria

✅ **Single-turn:** User provides order_id → agent returns status  
✅ **Multi-turn:** User asks vaguely → agent asks for order_id → user provides → agent returns status  
✅ **LLM-based:** Uses `LLMProvider` (OpenAI) for classification and planning  
✅ **Swappable primitives:** Can replace OpenAIProvider with AnthropicProvider in <5 lines  
✅ **Swappable data:** Can replace JSONDataSource with SQLiteDataSource in <5 lines  
✅ **Observable:** Telemetry logs all 10 stages with structured payloads  
✅ **Memory:** Conversation history stored and used for context in classification/planning  

---

## Open Questions

**Q: Should we mock LLMProvider for tests?**  
A: Yes. Create `MockLLMProvider` that returns deterministic responses for testing.

**Q: How do we handle token limits?**  
A: M1 ignores this. M6 adds conversation summarization.

**Q: Response formatting - template or LLM?**  
A: M1 uses simple string templates (f-strings). M2+ can call LLMProvider for natural response generation.

**Q: How do we prevent LLM hallucination in tool parameter extraction?**  
A: Use OpenAI function calling with strict schemas. Validate params in PolicyEngine before execution.

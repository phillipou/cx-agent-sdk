# ADR-001: Five Core Primitives

- Status: Proposed
- Date: 2025-10-13

## Context
We need a minimal yet realistic SDK to teach PMs how agent systems work in production. Composability, swapability, and testability are key. Heavy orchestration frameworks are out of scope.

## Decision
Define five protocols to isolate concerns and enable swapping without changing orchestration:
- DataSource: fetches domain data (orders, tickets).
- LLMProvider: model I/O (classification, tool selection) with function calling.
- PolicyEngine: validates actions against YAML rules.
- ToolExecutor: executes tools with validated params.
- TelemetrySink: persists traces, metrics, and violations.
AgentRouter composes these and maintains conversation context.

## Consequences
- Pros: clear boundaries, easy A/B of implementations, unit-testable with fakes, policy outside tools, strong observability.
- Cons: more interfaces to maintain; small overhead wiring components.

## Alternatives Considered
- Monolithic agent module (faster start, poor swapability).
- LangChain/LlamaIndex orchestration (powerful, but hides learning goals and adds dependency weight).
- Event-bus microservices (overkill for local SDK).

## References
- Docs/PRD.md (Goals, Milestones)

## Follow-ups
- Define minimal method signatures in `src/core/`.
- Provide JSON/SQLite/Mock API implementations.


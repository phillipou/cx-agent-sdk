#!/usr/bin/env python
from __future__ import annotations

"""Tiny demo that wires the agent components and runs a single interaction.

This version uses a real OpenAI provider through the `OpenAIProvider` adapter.
Requirements:
  - `pip install -r requirements.txt`
  - Environment: `OPENAI_API_KEY` (required), `OPENAI_MODEL` (optional; defaults
    to `gpt-4o-mini`).
"""

from src.core.types import Interaction
from src.agent.router import AgentRouter
from src.adapters.datasource.json_data_source import JSONDataSource
from src.adapters.policy.null_policy import NullPolicyEngine
from src.adapters.telemetry.print_sink import PrintSink
from src.adapters.executor.local_executor import LocalExecutor
from src.adapters.intents.yaml_registry import YAMLIntentsRegistry
from src.adapters.llm.openai_provider import OpenAIProvider
from src.adapters.classifier.llm_intent_classifier import LLMIntentClassifier
from src.adapters.planner.simple_planner import SimplePlanner
from src.adapters.memory.in_memory import InMemoryConversationMemory
from src.tools.check_order_status import make_check_order_status

# Load environment variables from .env if present (developer convenience)
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass


def main() -> None:
    """Wire components and run a single interaction end-to-end.

    This demo intentionally keeps dependencies minimal so you can see each
    component's role in the request lifecycle.
    """
    # Data and tools
    ds = JSONDataSource("data/orders.json")
    executor = LocalExecutor()
    executor.register("check_order_status", make_check_order_status(ds))

    # Policies and telemetry
    policy = NullPolicyEngine()
    telemetry = PrintSink()

    # Intents + classifier (LLM-based via OpenAI)
    intents = YAMLIntentsRegistry("config/intents.yaml")
    # Choose model per agent/function, not globally.
    llm = OpenAIProvider(model="gpt-4o-mini")
    classifier = LLMIntentClassifier(llm)
    planner = SimplePlanner()

    router = AgentRouter(
        intents=intents,
        classifier=classifier,
        planner=planner,
        policy=policy,
        executor=executor,
        telemetry=telemetry,
        memory=InMemoryConversationMemory(max_messages=10),
    )

    # Simulate a user asking for order status
    interaction: Interaction = {
        "id": "u-1",
        "text": "Where is my order O-12345?",
        "customer_id": "C-1",
        "context": {"session_id": "s-1", "channel": "chat"},
    }
    response = router.handle(interaction)
    print({"agent_response": response})


if __name__ == "__main__":
    main()

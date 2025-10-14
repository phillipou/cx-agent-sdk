from __future__ import annotations
from typing import List, Tuple, Dict

from src.core.interfaces import IntentClassifier, LLMProvider
from src.core.types import Interaction, Intent


class LLMIntentClassifier(IntentClassifier):
    """Classifies the user's intent and extracts slots using an LLM provider.

    Prompt structure:
      - The user message and recent history (if any)
      - The list of eligible intents (names + descriptions)

    Provider contract:
      - Returns a JSON-like dict: {"intent_id", "slots", "missing_slots", "confidence"}.
      - When the provider supports it, we request JSON mode via `response_format`.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def classify(
        self, interaction: Interaction, intents: List[Intent], history: List[dict]
    ) -> Tuple[Intent | None, Dict]:
        # Build a minimal system/user prompt. In real usage, you'd provide a JSON schema
        # or function-calling definition. Our FakeLLMProvider returns a structured dict.
        intents_desc = [
            f"- {it.get('id')}: {it.get('description')} (slots: {it.get('required_slots')})"
            for it in intents
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a classifier. Pick an intent from the provided list and extract required slots."
                ),
            },
            {"role": "user", "content": interaction.get("text", "")},
            {
                "role": "system",
                "content": "Eligible intents:\n" + "\n".join(intents_desc),
            },
        ]

        # Ask the provider for JSON output so parsing is reliable.
        result = self.llm.generate(messages, response_format={"type": "json_object"})
        intent_id = result.get("intent_id")
        slots = result.get("slots", {}) or {}

        # Map intent_id back to the full intent object
        intent = next((it for it in intents if it.get("id") == intent_id), None)
        return intent, slots

from __future__ import annotations
from typing import List, Tuple, Dict

from src.core.interfaces import IntentClassifier, LLMProvider
from src.core.types import Interaction, Intent


class LLMIntentClassifier(IntentClassifier):
    """Classifies the user's intent and extracts parameters using an LLM provider.

    Prompt structure:
      - The user message and recent history (if any)
      - The list of eligible intents (names + descriptions)

    Provider contract:
      - Returns a JSON-like dict: {"intent_id", "params", "missing_params", "confidence"}.
      - When the provider supports it, we request JSON mode via `response_format`.
    """

    def __init__(self, llm: LLMProvider) -> None:
        """Store the low-level LLM provider used for classification."""
        self.llm = llm

    def classify(
        self, interaction: Interaction, intents: List[Intent], history: List[dict]
    ) -> Tuple[Intent | None, Dict]:
        """Return the chosen intent and extracted parameters using the LLM.

        Builds a minimalist prompt with the user's message and eligible intents,
        asks the provider for JSON, and maps the `intent_id` back to the full
        intent definition.
        """
        # Build a minimal system/user prompt. In real usage, you'd provide a JSON schema
        # or function-calling definition. Our FakeLLMProvider returns a structured dict.
        intents_desc = [
            f"- {it.get('id')}: {it.get('description')} (params: {it.get('required_params')})"
            for it in intents
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a classifier. Pick an intent from the provided list and extract required parameters."
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
        params = result.get("params", {}) or {}

        # Map intent_id back to the full intent object
        intent = next((it for it in intents if it.get("id") == intent_id), None)
        return intent, params

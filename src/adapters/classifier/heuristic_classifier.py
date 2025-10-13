from __future__ import annotations
import re
from typing import List, Tuple, Dict

from src.core.interfaces import IntentClassifier
from src.core.types import Interaction, Intent


class HeuristicIntentClassifier(IntentClassifier):
    def classify(
        self, interaction: Interaction, intents: List[Intent], history: List[dict]
    ) -> Tuple[Intent | None, dict]:
        text = (interaction.get("text") or "").strip()
        if not intents:
            return None, {}
        # Simple heuristic: pick the first intent and try to fill slots via regex patterns from config
        # For M1, only `order_status` exists.
        best_intent = intents[0]
        slots: Dict[str, str] = {}
        slot_mapping = best_intent.get("slot_mapping", {}) or {}
        for slot, pattern in slot_mapping.items():
            try:
                m = re.search(pattern, text)
            except re.error:
                m = None
            if m:
                slots[slot] = m.group(0)
        return best_intent, slots


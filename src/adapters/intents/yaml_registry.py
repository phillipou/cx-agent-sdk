from __future__ import annotations
from typing import List, Dict, Any
from pathlib import Path
import yaml

from src.core.interfaces import IntentsRegistry
from src.core.types import Intent


class YAMLIntentsRegistry(IntentsRegistry):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._intents: List[Intent] = []
        self._load()

    def _load(self) -> None:
        data = yaml.safe_load(self.path.read_text()) or {}
        intents = data.get("intents", [])
        self._intents = intents

    def get_eligible(self, context: dict) -> List[Intent]:
        channel = (context or {}).get("channel", "chat")
        eligible: List[Intent] = []
        for it in self._intents:
            constraints: Dict[str, Any] = it.get("constraints", {}) or {}
            channels = constraints.get("channels")
            if channels and channel not in channels:
                continue
            # rollout, tiers can be added later; assume eligible
            eligible.append(it)
        return eligible


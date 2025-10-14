from __future__ import annotations
"""JSON-backed data source.

Loads a local JSON file containing a list of order dicts and exposes a simple
lookup by `order_id`. Intended for demos and tests.
"""
import json
from pathlib import Path
from typing import Optional
from src.core.interfaces import DataSource


class JSONDataSource(DataSource):
    """Read-only data source backed by a JSON file."""
    def __init__(self, orders_path: str | Path) -> None:
        self.orders_path = Path(orders_path)
        self._orders = None

    def _load(self) -> None:
        if self._orders is None:
            with self.orders_path.open() as f:
                self._orders = {o["order_id"]: o for o in json.load(f)}

    def get_order(self, order_id: str) -> dict | None:
        """Return an order dict by id or None if not found."""
        self._load()
        return self._orders.get(order_id)

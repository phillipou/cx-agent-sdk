from __future__ import annotations
from typing import Callable
from src.core.types import ToolResult
from src.core.interfaces import DataSource


def make_check_order_status(ds: DataSource) -> Callable[[dict], ToolResult]:
    def _handler(params: dict) -> ToolResult:
        order_id = params.get("order_id")
        if not order_id:
            return ToolResult(ok=False, error="missing order_id")
        order = ds.get_order(order_id)
        if not order:
            return ToolResult(ok=False, error="order_not_found")
        return ToolResult(ok=True, data=order)

    return _handler


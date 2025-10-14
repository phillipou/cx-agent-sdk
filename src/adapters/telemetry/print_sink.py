from __future__ import annotations
"""Simple telemetry sink that prints events.

For early development this makes the agent's behavior traceable in stdout.
In production, use a structured sink (e.g., HTTP, file, or metrics backend).
"""
from pprint import pprint
from src.core.interfaces import TelemetrySink
from src.core.types import TelemetryEvent


class PrintSink(TelemetrySink):
    def record(self, event: TelemetryEvent) -> None:
        pprint({k: v for k, v in event.items() if k != "timestamp"})

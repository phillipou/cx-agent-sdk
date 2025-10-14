from __future__ import annotations
"""Simple telemetry sink that prints events.

For early development this makes the agent's behavior traceable in stdout.
In production, use a structured sink (e.g., HTTP, file, or metrics backend).
"""
from pprint import pprint
from src.core.interfaces import TelemetrySink
from src.core.types import TelemetryEvent


class PrintSink(TelemetrySink):
    """Telemetry sink that prints structured events to stdout.

    Useful during development to observe the end-to-end flow without a DB.
    """

    def record(self, event: TelemetryEvent) -> None:
        """Pretty-print the event (without the raw timestamp)."""
        pprint({k: v for k, v in event.items() if k != "timestamp"})

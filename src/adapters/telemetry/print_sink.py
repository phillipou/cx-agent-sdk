from __future__ import annotations
from pprint import pprint
from src.core.interfaces import TelemetrySink
from src.core.types import TelemetryEvent


class PrintSink(TelemetrySink):
    def record(self, event: TelemetryEvent) -> None:
        pprint({k: v for k, v in event.items() if k != "timestamp"})


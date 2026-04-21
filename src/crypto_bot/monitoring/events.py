from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MetricsSink:
    counters: Counter[str] = field(default_factory=Counter)
    latencies_ms: list[float] = field(default_factory=list)

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def observe_latency(self, name: str, ms: float) -> None:
        self.latencies_ms.append(ms)
        logger.info("metric_latency", name=name, ms=ms)

    def snapshot(self) -> dict[str, Any]:
        return {
            "counters": dict(self.counters),
            "latency_samples": len(self.latencies_ms),
        }


def emit(event: str, **fields: Any) -> None:
    logger.info(event, **fields)

"""Open-loop fixed-rate latency harness (research 05, coordinated-omission-safe).

Requests are launched at scheduled wall-clock instants regardless of how the
service is doing; latency = done - scheduled_send, so a backed-up service is
charged its queueing delay (wrk2/vegeta semantics). HdrHistogram recording,
warmup discarded, fixed concurrency cap per run.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from hdrh.histogram import HdrHistogram

PERCENTILES = (50.0, 95.0, 99.0, 99.9)
_HIST_MAX_US = 600_000_000  # 10 minutes; anything above clamps, not crashes


@dataclass
class LatencyResult:
    rate_hz: float
    concurrency: int
    samples: int
    warmup: int
    recorded: int  # histogram count; == samples - errors when healthy
    errors: int  # failures inside the measured window only
    warmup_errors: int
    duration_s: float
    completion_hz: float  # total/duration incl. queue drain — not the arrival rate
    percentiles_ms: dict[str, float]
    max_ms: float

    def to_json(self) -> dict[str, object]:
        return self.__dict__ | {"percentiles_ms": dict(self.percentiles_ms)}


async def run_open_loop(
    request_fn: Callable[[int], Awaitable[None]],
    *,
    rate_hz: float,
    concurrency: int,
    samples: int,
    warmup: int,
) -> LatencyResult:
    """Fire warmup+samples requests at rate_hz; record the last `samples`."""
    hist = HdrHistogram(1, _HIST_MAX_US, 3)  # microsecond resolution
    sem = asyncio.Semaphore(concurrency)
    errors = 0
    warmup_errors = 0
    total = warmup + samples

    async def one(i: int, scheduled: float) -> None:
        nonlocal errors, warmup_errors
        try:
            async with sem:
                await request_fn(i)
        except Exception:
            if i >= warmup:
                errors += 1
            else:
                warmup_errors += 1
            return
        if i >= warmup:
            micros = int((time.perf_counter() - scheduled) * 1e6)
            hist.record_value(min(max(micros, 1), _HIST_MAX_US))

    t0 = time.perf_counter()
    tasks: list[asyncio.Task[None]] = []
    for i in range(total):
        scheduled = t0 + i / rate_hz
        delay = scheduled - time.perf_counter()
        if delay > 0:
            await asyncio.sleep(delay)
        # spawn without awaiting the semaphore: arrivals stay open-loop,
        # the queue wait lands inside the measured latency where it belongs
        tasks.append(asyncio.create_task(one(i, scheduled)))
    await asyncio.gather(*tasks)
    duration = time.perf_counter() - t0
    return LatencyResult(
        rate_hz=rate_hz,
        concurrency=concurrency,
        samples=samples,
        warmup=warmup,
        recorded=hist.total_count,
        errors=errors,
        warmup_errors=warmup_errors,
        duration_s=duration,
        completion_hz=total / duration,
        percentiles_ms={f"p{p:g}": hist.get_value_at_percentile(p) / 1000 for p in PERCENTILES},
        max_ms=hist.get_max_value() / 1000,
    )

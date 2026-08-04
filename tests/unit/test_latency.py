"""Open-loop harness: sample counts, error accounting, CO-safe timestamps."""

import asyncio

import pytest

from constellate.bench.latency import run_open_loop


def test_records_exactly_samples_and_discards_warmup() -> None:
    calls: list[int] = []

    async def request(i: int) -> None:
        calls.append(i)
        await asyncio.sleep(0.001)

    result = asyncio.run(
        run_open_loop(request, rate_hz=500, concurrency=4, samples=40, warmup=10)
    )
    assert len(calls) == 50
    assert result.samples == 40
    assert result.errors == 0
    assert result.percentiles_ms["p50"] >= 1.0  # each request sleeps 1ms
    assert result.percentiles_ms["p99"] >= result.percentiles_ms["p50"]
    assert result.achieved_hz == pytest.approx(500, rel=0.5)


def test_errors_counted_not_recorded() -> None:
    async def request(i: int) -> None:
        if i % 2:
            raise RuntimeError("boom")
        await asyncio.sleep(0)

    result = asyncio.run(run_open_loop(request, rate_hz=1000, concurrency=2, samples=20, warmup=0))
    assert result.errors == 10


def test_queueing_delay_is_charged() -> None:
    # concurrency 1 with 20ms service time at 200/s arrival: queue builds,
    # so late requests must be charged far more than their service time
    async def request(i: int) -> None:
        await asyncio.sleep(0.02)

    result = asyncio.run(run_open_loop(request, rate_hz=200, concurrency=1, samples=20, warmup=0))
    assert result.max_ms > 100  # queue wait dwarfs the 20ms service time

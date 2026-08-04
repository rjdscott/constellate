"""`make bench-smoke PLATFORM=lyra` — the three flows the explorer demos.

F1 similar:       seed item → fused vector+graph neighbours, explained
F2 personalised:  user history → top-N with exclusions applied
F3 cold start:    a probe-set cold item (thin ratings, genome tags) → similar

Not a benchmark — a proof the platform answers all three shapes end to end.
Phase 04 owns real measurement.
"""

import asyncio
import sys

import pandas as pd

from constellate.core.types import RetrievalRequest, RetrievalResponse
from constellate.factory import build_service
from constellate.ingest import CANONICAL_DIR


def _show(name: str, response: RetrievalResponse) -> None:
    if not response.recommendations:
        sys.exit(f"{name}: FAILED — no recommendations")
    top = ", ".join(str(r.metadata.get("title", r.item_id)) for r in response.recommendations[:3])
    t = response.timings
    print(
        f"{name}: {len(response.recommendations)} recs in {t.total_ms:.1f}ms "
        f"(rel {t.relational_ms:.1f} / vec {t.vector_ms:.1f} / graph {t.graph_ms:.1f} "
        f"/ fuse {t.fusion_ms:.1f}) [{response.config_fingerprint}]"
    )
    print(f"    top: {top}")
    reasons = [r.reason for r in response.recommendations if r.reason]
    if reasons:
        print(f"    reason: {reasons[0]}")


async def main(platform: str = "lyra") -> None:
    service = await build_service(platform)
    _show("F1 similar(318 Shawshank)", await service.similar(318, k=10, explain=True))
    _show(
        "F2 personalised(user 1)",
        await service.recommend(RetrievalRequest(user_id=1, k=10)),
    )
    probes = pd.read_parquet(CANONICAL_DIR / "probes.parquet")
    cold_seed = int(probes[probes["kind"] == "cold_start"].iloc[0]["seed_item_id"])
    _show(
        f"F3 cold-start({cold_seed})",
        await service.similar(cold_seed, k=10, explain=True),
    )
    print("smoke: all flows green")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "lyra"))

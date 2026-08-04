#!/usr/bin/env python3
"""Writes ui/public/snapshot/ from committed bench artifacts + platform
config, so `VITE_UI_MODE=snapshot pnpm build` produces a fully static build
(bench dashboards work with no API). stdlib only — this has nothing to do
that needs a dependency.

Must agree with ui/src/lib/api.ts's snapshot URL mapping: a GET path like
`/v1/bench-results/<name>` becomes `snapshot/bench-results/<name>.json` (the
`/v1/` prefix is stripped, everything after it — including slashes — becomes
the file path), so a nested route is a nested file, not a flat one.

Run: `make ui-snapshot` (`uv run python scripts/build_ui_snapshot.py`).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "config"  # config/*.yaml stems ARE the platform registry (app.py agrees)
RESULTS_DIR = REPO_ROOT / "bench" / "results"
TAGS_PATH = REPO_ROOT / "data" / "raw" / "ml-25m" / "genome-tags.csv"
SNAPSHOT_DIR = REPO_ROOT / "ui" / "public" / "snapshot"


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def build() -> None:
    platforms = sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))
    artifact_paths = sorted(RESULTS_DIR.glob("*.json"))  # same ordering as GET /v1/bench-results

    listing: list[dict[str, object]] = []
    for path in artifact_paths:
        raw = json.loads(path.read_text())
        listing.append(
            {
                "name": path.stem,
                "platform": raw.get("platform"),
                "config_fingerprint": raw.get("config_fingerprint"),
                "utc": raw.get("utc"),
            }
        )
        _write_json(SNAPSHOT_DIR / "bench-results" / f"{path.stem}.json", raw)
    _write_json(SNAPSHOT_DIR / "bench-results.json", listing)

    # No live API in a snapshot build, so every platform reports alive:false;
    # its fingerprint is the most recent artifact's, not a health probe.
    platform_rows = []
    for platform in platforms:
        candidates = [e for e in listing if e["platform"] == platform]
        latest = max(candidates, key=lambda e: str(e["utc"] or "")) if candidates else None
        platform_rows.append(
            {
                "platform": platform,
                "alive": False,
                "config_fingerprint": latest["config_fingerprint"] if latest else None,
            }
        )
    _write_json(SNAPSHOT_DIR / "platforms.json", platform_rows)

    if TAGS_PATH.is_file():
        with TAGS_PATH.open(newline="") as f:
            tags = {row["tagId"]: row["tag"] for row in csv.DictReader(f)}
        _write_json(SNAPSHOT_DIR / "tags.json", tags)

    print(
        f"snapshot written: {len(listing)} bench artifact(s), "
        f"{len(platform_rows)} platform(s) → {SNAPSHOT_DIR}"
    )


if __name__ == "__main__":
    build()

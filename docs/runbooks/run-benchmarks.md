# Run the benchmark suite

## When to use

Producing (or reproducing) a committed benchmark artifact for a platform —
quality ablation, fusion tuning, F1–F6 flow checks, open-loop latency — and
regenerating `bench/report.md`. Phase 04's go/no-go verdict comes from here.

## Steps

1. Prerequisites: canonical data + platform artifacts exist.

   ```sh
   make seed                 # no-op if data/canonical/ is complete
   make load PLATFORM=lyra   # no-op if data/lyra/ is complete
   ```

2. Full run (quality + flows + latency; latency alone is ~15 min *per run*,
   ~1 h total — each of 4 runs fires ≥5,000 open-loop samples and Lyra's
   measured capacity is single-digit requests/second):

   ```sh
   make bench PLATFORM=lyra
   ```

   Quick iteration — skip latency or shrink samples:

   ```sh
   make bench PLATFORM=lyra BENCH_ARGS="--skip-latency"
   make bench PLATFORM=lyra BENCH_ARGS="--samples 1000 --warmup 100"
   ```

   Expected output ends with the artifact path:

   ```
   artifact: .../bench/results/lyra-<sha>-<utc>.json
   ```

3. Regenerate the report over all committed results:

   ```sh
   make report
   ```

   Prints the per-run verdict (`GO` / `NO-GO`) and writes `bench/report.md`.

4. Commit both the results JSON and `bench/report.md` — results are
   first-class repo artifacts, one file per run, never overwritten.

## What the artifact contains

- `flows`: F1–F6 hard checks (pass/fail + failures).
- `quality`: 200 graph-necessary probes × 3 arms (`vector_only`,
  `graph_only`, `hybrid` — the pipeline's `planes` subset), ir_measures
  Recall@10/50, nDCG@10, RR@10 overall + per probe kind, ranx paired
  significance, hand-rolled coverage/novelty.
- `fusion_tuning`: weighted-RRF graph-weight grid on a validation half,
  tuned with the pipeline's own `rrf` at the pipeline's fusion depth
  (`candidate_multiplier × k` per plane). The `fidelity_check` field proves
  the offline w=1.0 baseline reproduces the hybrid arm — only then does the
  winning weight transfer to `config/<platform>.yaml` `fusion.weights`.
- `latency`: open-loop fixed-rate runs (concurrency 1/8/32 at ~70% of
  measured capacity, plus one past-the-knee saturation run), HdrHistogram
  percentiles, latency = done − scheduled_send (coordinated-omission-safe).
  `latency_indicative: true` for Lyra — in-process, no network hop.

## Failure modes

- **`no lyra artifacts — run make seed && make load`** — the factory refused
  to start; run the two commands from step 1.
- **Latency percentiles explode (seconds, not ms)** — expected for the
  saturation run (last row): arrival rate is set to 1.2× measured capacity
  and queueing delay is charged from the scheduled send time. Only worry if
  the *sub-capacity* rows do this too.
- **Run duration surprises you** — sample count trades against p99 trust:
  fewer than ~5,000 samples makes the p99 row decorative (research 05).
  Use `--skip-latency` while iterating, never for a committed artifact.

## Last verified

2026-08-04 — phase 04, Lyra on the 28-core/62GB dev box.

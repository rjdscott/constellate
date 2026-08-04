# Constellate benchmark report

## lyra-c368e54-20260804T071640Z

- platform `lyra` · sha `c368e54` · 2026-08-04T07:16:40+00:00 · config `2575edad6710adae`
- flows: F1 ok, F2 ok, F3 ok, F4 ok, F5 ok, F6 ok

### Verdict: **GO** — hybrid beats vector-only on Recall@10 by +0.0141 (p=0.005411)

### Quality (200 graph-necessary probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0213 | 0.0439 | 0.0273 | 0.0746 | 0.0274 | 17.37 |
| graph_only | 0.0965 | 0.3516 | 0.0752 | 0.1025 | 0.0172 | 13.04 |
| hybrid | 0.0355 | 0.2301 | 0.0362 | 0.0844 | 0.0249 | 15.41 |

#### By probe kind

| probe kind | vector_only R@10 | graph_only R@10 | hybrid R@10 |
|---|---|---|---|
| cold_start | 0.0680 | 0.0300 | 0.0660 |
| cross_genre | 0.0020 | 0.3520 | 0.0666 |
| path_required | 0.0060 | 0.0040 | 0.0020 |
| tag_bridge | 0.0093 | 0.0000 | 0.0073 |

### Fusion tuning (weighted RRF, validation half)

Best graph weight **1.5** on nDCG@10 (baseline 1.0). Held-out test half: baseline nDCG@10 0.0418 vs tuned 0.0479.

### Latency (open-loop, coordinated-omission-safe)

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 114.83ms, est. capacity 8.7/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | p99.9ms | max ms | errors |
|---|---|---|---|---|---|---|---|---|
| 6.1 | 1 | 5000 | 127.7 | 156.0 | 173.3 | 206.3 | 234.2 | 0 |
| 6.1 | 8 | 5000 | 126.6 | 152.3 | 166.8 | 188.4 | 197.4 | 0 |
| 6.1 | 32 | 5000 | 126.3 | 151.3 | 166.1 | 185.9 | 216.1 | 0 |
| 10.5 | 32 | 5000 | 61440.0 | 107544.6 | 111542.3 | 113311.7 | 113770.5 | 0 |

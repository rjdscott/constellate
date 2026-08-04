# Constellate benchmark report

## lyra-f7eb799-20260804T082917Z

- platform `lyra` · sha `f7eb799` · 2026-08-04T08:29:17+00:00 · config `2575edad6710adae`
- flows: F1 ok, F2 ok, F3 ok, F4 ok, F5 ok, F6 ok

### Verdict: **GO** — hybrid beats vector-only on Recall@10 by +0.0141 (p=0.005411)

### Quality (200 graph-necessary probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0213 | 0.0439 | 0.0273 | 0.0746 | 0.0274 | 17.45 |
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

Best graph weight **2.0** on nDCG@10 (baseline 1.0). Held-out test half: baseline nDCG@10 0.0391 vs tuned 0.0486.

### Latency (open-loop, coordinated-omission-safe)

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 118.04ms, est. capacity 8.5/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 5.9 | 1 | 5000 | 128.2 | 153.9 | 168.2 | 231.7 | 0 |
| 5.9 | 8 | 5000 | 128.4 | 154.8 | 169.2 | 198.5 | 0 |
| 5.9 | 32 | 5000 | 128.4 | 154.2 | 166.8 | 202.9 | 0 |
| 10.2 | 32 | 5000 | 54231.0 | 93192.2 | 96665.6 | 98762.8 | 0 |

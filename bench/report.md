# Constellate benchmark report

| run | platform | graph | sha | hybrid R@10 | delta vs vector | verdict |
|---|---|---|---|---|---|---|
| lyra-f7eb799-20260804T082917Z | lyra | - | f7eb799 | 0.0355 | +0.0141 | GO |
| orion-8187751-20260804T101625Z | orion | cte | 8187751 | 0.0376 | +0.0267 | GO |
| orion-e3526c7-20260804T110915Z | orion | age | e3526c7 | 0.0376 | +0.0267 | GO |

## Cross-platform quality equivalence (hybrid arm, vs Lyra)

| run | R@10 | nDCG@10 | tolerance | verdict |
|---|---|---|---|---|
| orion-8187751-20260804T101625Z | +0.0021 | +0.0002 | ±0.02 | within |
| orion-e3526c7-20260804T110915Z | +0.0021 | +0.0002 | ±0.02 | within |

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

## orion-8187751-20260804T101625Z

- platform `orion` · sha `8187751` · 2026-08-04T10:16:25+00:00 · config `21fa5e19b24643dc`
- flows: F1 ok, F2 ok, F3 ok, F4 ok, F5 ok, F6 ok

### Verdict: **GO** — hybrid beats vector-only on Recall@10 by +0.0267 (p=4.145e-06)

### Quality (200 graph-necessary probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0108 | 0.0242 | 0.0127 | 0.0311 | 0.0192 | 19.49 |
| graph_only | 0.0965 | 0.3516 | 0.0752 | 0.1025 | 0.0172 | 13.04 |
| hybrid | 0.0376 | 0.2473 | 0.0364 | 0.0793 | 0.0202 | 16.44 |

#### By probe kind

| probe kind | vector_only R@10 | graph_only R@10 | hybrid R@10 |
|---|---|---|---|
| cold_start | 0.0300 | 0.0300 | 0.0440 |
| cross_genre | 0.0000 | 0.3520 | 0.0989 |
| path_required | 0.0060 | 0.0040 | 0.0020 |
| tag_bridge | 0.0073 | 0.0000 | 0.0053 |

### Fusion tuning (weighted RRF, validation half)

Best graph weight **2.0** on nDCG@10 (baseline 1.0). Held-out test half: baseline nDCG@10 0.0423 vs tuned 0.0671.

### Latency (open-loop, coordinated-omission-safe)

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 38.11ms, est. capacity 26.2/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 18.4 | 1 | 5000 | 46.7 | 81.7 | 100.3 | 117.3 | 0 |
| 18.4 | 8 | 5000 | 43.4 | 78.3 | 109.2 | 212.2 | 0 |
| 18.4 | 32 | 5000 | 43.6 | 75.4 | 90.2 | 160.8 | 0 |
| 31.5 | 32 | 5000 | 40.8 | 73.8 | 104.5 | 234.1 | 0 |

## orion-e3526c7-20260804T110915Z

- platform `orion` · sha `e3526c7` · 2026-08-04T11:09:15+00:00 · config `2a486f229ad267a7`
- flows: F1 ok, F2 ok, F3 ok, F4 ok, F5 ok, F6 ok

### Verdict: **GO** — hybrid beats vector-only on Recall@10 by +0.0267 (p=4.145e-06)

### Quality (200 graph-necessary probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0108 | 0.0242 | 0.0127 | 0.0311 | 0.0192 | 19.49 |
| graph_only | 0.0965 | 0.3516 | 0.0752 | 0.1025 | 0.0172 | 13.04 |
| hybrid | 0.0376 | 0.2473 | 0.0364 | 0.0793 | 0.0202 | 16.44 |

#### By probe kind

| probe kind | vector_only R@10 | graph_only R@10 | hybrid R@10 |
|---|---|---|---|
| cold_start | 0.0300 | 0.0300 | 0.0440 |
| cross_genre | 0.0000 | 0.3520 | 0.0989 |
| path_required | 0.0060 | 0.0040 | 0.0020 |
| tag_bridge | 0.0073 | 0.0000 | 0.0053 |

### Fusion tuning (weighted RRF, validation half)

Best graph weight **2.0** on nDCG@10 (baseline 1.0). Held-out test half: baseline nDCG@10 0.0423 vs tuned 0.0671.

### Latency (open-loop, coordinated-omission-safe)

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 221.1ms, est. capacity 4.5/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 3.2 | 1 | 2000 | 248.7 | 363.8 | 426.5 | 510.7 | 0 |
| 3.2 | 8 | 2000 | 249.6 | 365.1 | 434.2 | 505.6 | 0 |
| 3.2 | 32 | 2000 | 243.8 | 356.6 | 426.5 | 502.5 | 0 |
| 5.4 | 32 | 2000 | 259.1 | 428.3 | 480.5 | 547.3 | 0 |

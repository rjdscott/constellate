# Constellate benchmark report

| run | platform | graph | arm | sha | hybrid R@10 | delta vs vector | verdict |
|---|---|---|---|---|---|---|---|
| hydra-0b36d7c-20260804T134236Z | hydra | memgraph | svd | 0b36d7c | 0.0338 | +0.0138 | GO |
| hydra-fa9623e-20260805T035422Z | hydra | memgraph | svd | fa9623e | 0.0338 | +0.0138 | GO |
| hydra-fa9623e-20260805T044906Z | hydra | memgraph | neural | fa9623e | 0.0321 | +0.0176 | GO |
| lyra-f7eb799-20260804T082917Z | lyra | - | svd | f7eb799 | 0.0355 | +0.0141 | GO |
| lyra-fa9623e-20260805T012152Z | lyra | - | svd | fa9623e | 0.0355 | +0.0141 | GO |
| lyra-fa9623e-20260805T022106Z | lyra | - | neural | fa9623e | 0.0321 | +0.0176 | GO |
| orion-8187751-20260804T101625Z | orion | cte | svd | 8187751 | 0.0376 | +0.0267 | GO |
| orion-e3526c7-20260804T110915Z | orion | age | svd | e3526c7 | 0.0376 | +0.0267 | GO |
| orion-fa9623e-20260805T023925Z | orion | cte | svd | fa9623e | 0.0376 | +0.0267 | GO |
| orion-fa9623e-20260805T030508Z | orion | cte | neural | fa9623e | 0.0321 | +0.0176 | GO |

## Cross-platform quality equivalence (hybrid arm, vs Lyra) — neural

| run | R@10 | nDCG@10 | tolerance | verdict |
|---|---|---|---|---|
| hydra-fa9623e-20260805T044906Z | +0.0000 | +0.0000 | ±0.02 | within |
| orion-fa9623e-20260805T030508Z | +0.0000 | +0.0000 | ±0.02 | within |

## Cross-platform quality equivalence (hybrid arm, vs Lyra) — svd

| run | R@10 | nDCG@10 | tolerance | verdict |
|---|---|---|---|---|
| hydra-0b36d7c-20260804T134236Z | -0.0017 | -0.0025 | ±0.02 | within |
| hydra-fa9623e-20260805T035422Z | -0.0017 | -0.0025 | ±0.02 | within |
| orion-8187751-20260804T101625Z | +0.0021 | +0.0002 | ±0.02 | within |
| orion-e3526c7-20260804T110915Z | +0.0021 | +0.0002 | ±0.02 | within |
| orion-fa9623e-20260805T023925Z | +0.0021 | +0.0002 | ±0.02 | within |

## Embedding arm ablation (svd vs neural)

### hydra

Native embedding coverage: svd 0.2213, neural 1.0000.

| retrieval arm | R@10 svd | R@10 neural | delta | nDCG@10 svd | nDCG@10 neural | delta |
|---|---|---|---|---|---|---|
| vector_only | 0.0200 | 0.0145 | -0.0055 | 0.0238 | 0.0186 | -0.0053 |
| graph_only | 0.0965 | 0.0965 | +0.0000 | 0.0752 | 0.0752 | +0.0000 |
| hybrid | 0.0338 | 0.0321 | -0.0017 | 0.0337 | 0.0310 | -0.0027 |

Genome subset (200 probes, fallback vectors excluded):

| retrieval arm | R@10 svd | R@10 neural | delta | nDCG@10 svd | nDCG@10 neural | delta |
|---|---|---|---|---|---|---|
| vector_only | 0.0200 | 0.0145 | -0.0055 | 0.0238 | 0.0186 | -0.0053 |
| graph_only | 0.0965 | 0.0965 | +0.0000 | 0.0752 | 0.0752 | -0.0000 |
| hybrid | 0.0338 | 0.0321 | -0.0017 | 0.0337 | 0.0310 | -0.0027 |

### lyra

Native embedding coverage: svd 0.2213, neural 1.0000.

| retrieval arm | R@10 svd | R@10 neural | delta | nDCG@10 svd | nDCG@10 neural | delta |
|---|---|---|---|---|---|---|
| vector_only | 0.0213 | 0.0145 | -0.0068 | 0.0273 | 0.0186 | -0.0087 |
| graph_only | 0.0965 | 0.0965 | +0.0000 | 0.0752 | 0.0752 | +0.0000 |
| hybrid | 0.0355 | 0.0321 | -0.0034 | 0.0362 | 0.0310 | -0.0052 |

Genome subset (200 probes, fallback vectors excluded):

| retrieval arm | R@10 svd | R@10 neural | delta | nDCG@10 svd | nDCG@10 neural | delta |
|---|---|---|---|---|---|---|
| vector_only | 0.0213 | 0.0145 | -0.0068 | 0.0273 | 0.0186 | -0.0087 |
| graph_only | 0.0965 | 0.0965 | -0.0000 | 0.0752 | 0.0752 | +0.0000 |
| hybrid | 0.0355 | 0.0321 | -0.0034 | 0.0362 | 0.0310 | -0.0052 |

### orion

Native embedding coverage: svd 0.2213, neural 1.0000.

| retrieval arm | R@10 svd | R@10 neural | delta | nDCG@10 svd | nDCG@10 neural | delta |
|---|---|---|---|---|---|---|
| vector_only | 0.0108 | 0.0145 | +0.0037 | 0.0127 | 0.0186 | +0.0059 |
| graph_only | 0.0965 | 0.0965 | +0.0000 | 0.0752 | 0.0752 | +0.0000 |
| hybrid | 0.0376 | 0.0321 | -0.0054 | 0.0364 | 0.0310 | -0.0054 |

Genome subset (200 probes, fallback vectors excluded):

| retrieval arm | R@10 svd | R@10 neural | delta | nDCG@10 svd | nDCG@10 neural | delta |
|---|---|---|---|---|---|---|
| vector_only | 0.0108 | 0.0145 | +0.0037 | 0.0127 | 0.0186 | +0.0059 |
| graph_only | 0.0965 | 0.0965 | +0.0000 | 0.0752 | 0.0752 | +0.0000 |
| hybrid | 0.0376 | 0.0321 | -0.0054 | 0.0364 | 0.0310 | -0.0054 |

## hydra-0b36d7c-20260804T134236Z

- platform `hydra` · sha `0b36d7c` · 2026-08-04T13:42:36+00:00 · config `3e16e0cd60325e98` · arm `svd`
- flows: F1 ok, F2 ok, F3 ok, F4 ok, F5 ok, F6 ok

### Verdict: **GO** — hybrid beats vector-only on Recall@10 by +0.0138 (p=0.003825)

### Quality (200 graph-necessary probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0200 | 0.0366 | 0.0238 | 0.0625 | 0.0279 | 17.29 |
| graph_only | 0.0965 | 0.3516 | 0.0752 | 0.1025 | 0.0172 | 13.04 |
| hybrid | 0.0338 | 0.2377 | 0.0337 | 0.0744 | 0.0252 | 15.35 |

#### By probe kind

| probe kind | vector_only R@10 | graph_only R@10 | hybrid R@10 |
|---|---|---|---|
| cold_start | 0.0580 | 0.0300 | 0.0620 |
| cross_genre | 0.0087 | 0.3520 | 0.0619 |
| path_required | 0.0060 | 0.0040 | 0.0040 |
| tag_bridge | 0.0073 | 0.0000 | 0.0073 |

### Fusion tuning (weighted RRF, validation half)

Best graph weight **2.0** on nDCG@10 (baseline 1.0). Held-out test half: baseline nDCG@10 0.0329 vs tuned 0.0417.

### Latency (open-loop, coordinated-omission-safe)

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 103.84ms, est. capacity 9.6/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 6.7 | 1 | 5000 | 114.7 | 165.2 | 193.8 | 239.5 | 0 |
| 6.7 | 8 | 5000 | 115.1 | 171.1 | 199.7 | 279.8 | 0 |
| 6.7 | 32 | 5000 | 114.6 | 170.5 | 198.7 | 269.1 | 0 |
| 11.6 | 32 | 5000 | 109.9 | 160.8 | 193.2 | 246.9 | 0 |

## hydra-fa9623e-20260805T035422Z

- platform `hydra` · sha `fa9623e` · 2026-08-05T03:54:21+00:00 · config `a0e767ae42aae802` · arm `svd`
- flows: F1 ok, F2 ok, F3 ok, F4 ok, F5 ok, F6 ok

### Verdict: **GO** — hybrid beats vector-only on Recall@10 by +0.0138 (p=0.003825)

### Quality (200 graph-necessary probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0200 | 0.0366 | 0.0238 | 0.0625 | 0.0279 | 17.29 |
| graph_only | 0.0965 | 0.3516 | 0.0752 | 0.1025 | 0.0172 | 13.04 |
| hybrid | 0.0338 | 0.2377 | 0.0337 | 0.0744 | 0.0252 | 15.35 |

#### By probe kind

| probe kind | vector_only R@10 | graph_only R@10 | hybrid R@10 |
|---|---|---|---|
| cold_start | 0.0580 | 0.0300 | 0.0620 |
| cross_genre | 0.0087 | 0.3520 | 0.0619 |
| path_required | 0.0060 | 0.0040 | 0.0040 |
| tag_bridge | 0.0073 | 0.0000 | 0.0073 |

### Fusion tuning (weighted RRF, validation half)

Best graph weight **2.0** on nDCG@10 (baseline 1.0). Held-out test half: baseline nDCG@10 0.0329 vs tuned 0.0417.

### Latency (open-loop, coordinated-omission-safe)

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 100.77ms, est. capacity 9.9/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 6.9 | 1 | 5000 | 115.1 | 168.1 | 196.5 | 667.6 | 0 |
| 6.9 | 8 | 5000 | 112.4 | 167.0 | 193.2 | 234.4 | 0 |
| 6.9 | 32 | 5000 | 112.1 | 166.1 | 194.2 | 255.0 | 0 |
| 11.9 | 32 | 5000 | 105.5 | 155.3 | 186.6 | 251.0 | 0 |

## hydra-fa9623e-20260805T044906Z

- platform `hydra` · sha `fa9623e` · 2026-08-05T04:49:06+00:00 · config `17de02ea68e77ba1` · arm `neural`
- flows: F1 ok, F2 ok, F3 ok, F4 ok, F5 ok, F6 ok

### Verdict: **GO** — hybrid beats vector-only on Recall@10 by +0.0176 (p=0.0003828)

### Quality (200 graph-necessary probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0145 | 0.0596 | 0.0186 | 0.0513 | 0.0273 | 16.33 |
| graph_only | 0.0965 | 0.3516 | 0.0752 | 0.1025 | 0.0172 | 13.04 |
| hybrid | 0.0321 | 0.2331 | 0.0310 | 0.0740 | 0.0243 | 14.52 |

#### By probe kind

| probe kind | vector_only R@10 | graph_only R@10 | hybrid R@10 |
|---|---|---|---|
| cold_start | 0.0500 | 0.0300 | 0.0640 |
| cross_genre | 0.0020 | 0.3520 | 0.0471 |
| path_required | 0.0020 | 0.0040 | 0.0080 |
| tag_bridge | 0.0040 | 0.0000 | 0.0093 |

### Fusion tuning (weighted RRF, validation half)

Best graph weight **2.0** on nDCG@10 (baseline 1.0). Held-out test half: baseline nDCG@10 0.0404 vs tuned 0.0512.

### Latency (open-loop, coordinated-omission-safe)

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 111.57ms, est. capacity 9.0/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 6.3 | 1 | 5000 | 114.9 | 166.7 | 198.9 | 562.2 | 0 |
| 6.3 | 8 | 5000 | 113.5 | 167.4 | 192.9 | 253.3 | 0 |
| 6.3 | 32 | 5000 | 112.8 | 166.8 | 195.5 | 226.3 | 0 |
| 10.8 | 32 | 5000 | 104.1 | 152.8 | 180.1 | 229.9 | 0 |

## lyra-f7eb799-20260804T082917Z

- platform `lyra` · sha `f7eb799` · 2026-08-04T08:29:17+00:00 · config `2575edad6710adae` · arm `svd`
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

## lyra-fa9623e-20260805T012152Z

- platform `lyra` · sha `fa9623e` · 2026-08-05T01:21:52+00:00 · config `8ca079def5c580df` · arm `svd`
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

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 116.9ms, est. capacity 8.6/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 6.0 | 1 | 5000 | 129.3 | 156.8 | 176.8 | 419.8 | 0 |
| 6.0 | 8 | 5000 | 126.7 | 153.7 | 170.8 | 597.5 | 0 |
| 6.0 | 32 | 5000 | 129.2 | 157.1 | 173.3 | 235.1 | 0 |
| 10.3 | 32 | 5000 | 62521.3 | 105054.2 | 108920.8 | 110690.3 | 0 |

## lyra-fa9623e-20260805T022106Z

- platform `lyra` · sha `fa9623e` · 2026-08-05T02:21:06+00:00 · config `d506a5a45199671a` · arm `neural`
- flows: F1 ok, F2 ok, F3 ok, F4 ok, F5 ok, F6 ok

### Verdict: **GO** — hybrid beats vector-only on Recall@10 by +0.0176 (p=0.0003828)

### Quality (200 graph-necessary probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0145 | 0.0596 | 0.0186 | 0.0513 | 0.0273 | 16.34 |
| graph_only | 0.0965 | 0.3516 | 0.0752 | 0.1025 | 0.0172 | 13.04 |
| hybrid | 0.0321 | 0.2331 | 0.0310 | 0.0740 | 0.0243 | 14.53 |

#### By probe kind

| probe kind | vector_only R@10 | graph_only R@10 | hybrid R@10 |
|---|---|---|---|
| cold_start | 0.0500 | 0.0300 | 0.0640 |
| cross_genre | 0.0020 | 0.3520 | 0.0471 |
| path_required | 0.0020 | 0.0040 | 0.0080 |
| tag_bridge | 0.0040 | 0.0000 | 0.0093 |

### Fusion tuning (weighted RRF, validation half)

Best graph weight **2.0** on nDCG@10 (baseline 1.0). Held-out test half: baseline nDCG@10 0.0404 vs tuned 0.0512.

### Latency (open-loop, coordinated-omission-safe)

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 116.97ms, est. capacity 8.5/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 6.0 | 1 | 5000 | 128.5 | 155.4 | 174.2 | 539.6 | 0 |
| 6.0 | 8 | 5000 | 130.5 | 159.0 | 174.0 | 199.2 | 0 |
| 6.0 | 32 | 5000 | 131.2 | 158.6 | 172.8 | 205.3 | 0 |
| 10.3 | 32 | 5000 | 63602.7 | 108724.2 | 112918.5 | 114753.5 | 0 |

## orion-8187751-20260804T101625Z

- platform `orion` · sha `8187751` · 2026-08-04T10:16:25+00:00 · config `21fa5e19b24643dc` · arm `svd`
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

- platform `orion` · sha `e3526c7` · 2026-08-04T11:09:15+00:00 · config `2a486f229ad267a7` · arm `svd`
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

## orion-fa9623e-20260805T023925Z

- platform `orion` · sha `fa9623e` · 2026-08-05T02:39:25+00:00 · config `cbb9be4970564149` · arm `svd`
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

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 37.45ms, est. capacity 26.7/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 18.7 | 1 | 5000 | 46.0 | 85.4 | 105.4 | 247.4 | 0 |
| 18.7 | 8 | 5000 | 43.1 | 73.9 | 87.9 | 158.6 | 0 |
| 18.7 | 32 | 5000 | 43.1 | 74.7 | 88.4 | 109.1 | 0 |
| 32.0 | 32 | 5000 | 40.1 | 68.4 | 84.6 | 107.6 | 0 |

## orion-fa9623e-20260805T030508Z

- platform `orion` · sha `fa9623e` · 2026-08-05T03:05:08+00:00 · config `5b503701e4074c76` · arm `neural`
- flows: F1 ok, F2 ok, F3 ok, F4 ok, F5 ok, F6 ok

### Verdict: **GO** — hybrid beats vector-only on Recall@10 by +0.0176 (p=0.0003828)

### Quality (200 graph-necessary probes)

| arm | R@10 | R@50 | nDCG@10 | RR@10 | coverage | novelty |
|---|---|---|---|---|---|---|
| vector_only | 0.0145 | 0.0591 | 0.0186 | 0.0513 | 0.0273 | 16.32 |
| graph_only | 0.0965 | 0.3516 | 0.0752 | 0.1025 | 0.0172 | 13.04 |
| hybrid | 0.0321 | 0.2332 | 0.0310 | 0.0740 | 0.0243 | 14.53 |

#### By probe kind

| probe kind | vector_only R@10 | graph_only R@10 | hybrid R@10 |
|---|---|---|---|
| cold_start | 0.0500 | 0.0300 | 0.0640 |
| cross_genre | 0.0020 | 0.3520 | 0.0471 |
| path_required | 0.0020 | 0.0040 | 0.0080 |
| tag_bridge | 0.0040 | 0.0000 | 0.0093 |

### Fusion tuning (weighted RRF, validation half)

Best graph weight **2.0** on nDCG@10 (baseline 1.0). Held-out test half: baseline nDCG@10 0.0404 vs tuned 0.0518.

### Latency (open-loop, coordinated-omission-safe)

Workload: hybrid similar(seed), k=10, probe seeds round-robin — warm mean 36.68ms, est. capacity 27.3/s. **Indicative**: in-process, no network hop.

| rate/s | conc | samples | p50ms | p95ms | p99ms | max ms | errors |
|---|---|---|---|---|---|---|---|
| 19.1 | 1 | 5000 | 46.6 | 83.5 | 101.6 | 136.1 | 0 |
| 19.1 | 8 | 5000 | 42.9 | 73.9 | 88.8 | 114.3 | 0 |
| 19.1 | 32 | 5000 | 43.0 | 73.9 | 89.2 | 109.2 | 0 |
| 32.7 | 32 | 5000 | 39.7 | 67.3 | 83.2 | 116.3 | 0 |

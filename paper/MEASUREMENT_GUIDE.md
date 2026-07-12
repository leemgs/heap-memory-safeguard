# HMS — Measurement Guide for the Five Outstanding Experiments

This guide tells you, for every red `--` cell in the evaluation tables, exactly which
Android/Linux data source produces the number and how to compute it. Nothing here is a
fabricated result; it is the collection procedure so your measured values are defensible.

Primary tooling (collect once, reuse for all tables):
- **Perfetto** system trace with ftrace events: `vmscan/*`, `mm_event/*`, `kmem/*`,
  `sched/*`, `psi/*`; data sources: `linux.process_stats`, `linux.sys_stats`
  (period_ms=1000, meminfo + vmstat + PSI), and the **ART** data source (GC slices).
- **dumpsys**: `dumpsys meminfo <pkg>`, `dumpsys gfxinfo <pkg> framestats`.
- **/proc and /sys**: `/proc/<pid>/smaps_rollup`, `/proc/<pid>/stat`, `/proc/vmstat`,
  `/proc/pressure/memory`, per-memcg `memory.stat`, `/sys/block/zram0/mm_stat`.

---

## Column → data source → computation

| Metric (column) | Source | How to compute |
|---|---|---|
| **Peak RSS (MB)** | `/proc/<pid>/smaps_rollup` (`Rss:`) sampled at 1 Hz, or Perfetto `process_memory` counter | max over the run; sum target process + its native helper processes |
| **$L_r$ reclaim latency (ms)** | vmscan tracepoints `mm_vmscan_direct_reclaim_begin/end` (or your Enforcer's own ktime at ioctl-entry and shrinker-pass-done) | mean of (end − begin) per reclaim episode |
| **$T_{gc}$ GC pause (ms)** | Perfetto ART data source (GC pause slices) or logcat `dalvikvm`/`art` GC lines | mean stop-the-world pause per GC over the run |
| **Major faults (/min)** | `/proc/<pid>/stat` field 12 (`majflt`) delta, or `/proc/vmstat pgmajfault` for system-wide | (end − start) / run-minutes |
| **p99 frame time (ms)** | `dumpsys gfxinfo <pkg> framestats` or Perfetto FrameTimeline | 99th percentile of per-frame total duration |
| **Reclaimed pages / vol.** | `/proc/vmstat` `pgsteal_*` (pages) or per-memcg `memory.stat pgsteal`; MB = pages × 4 KiB | delta over the run; convert to MB for the "vol." columns |
| **$S_h$ heap stability (0–1)** | RSS time series (as above) | use your paper's definition (avg steady-state heap ÷ max heap); report in [0,1] |
| **zRAM activity** | `/sys/block/zram0/mm_stat` (`orig_data_size`, `compr_data_size`, read/write counts) | delta over the run; ratio gives compression, reads give re-touch cost |

---

## Experiment 1 — Static-Aggressive baseline (Table `tab:isolate`)

**Goal:** show HMS's edge is *coordination*, not just earlier/more reclaim.

**Build the baseline (no HMS, no `H_u`, no runtime telemetry):** make stock kernel reclaim
fire earlier and harder using static knobs only:
- raise `vm.watermark_scale_factor` (earlier kswapd wakeups),
- raise `vm.min_free_kbytes` / `vm.extra_free_kbytes`,
- optionally lower LMKD/PSI thresholds (`ro.lmk.*` props or `/proc/pressure/memory` triggers).

Run stock **Baseline**, **Static-Aggressive**, and **HMS** on W1–W4; average the six columns.
**Fairness control:** tune Static-Aggressive so its *total reclaim volume* is ≥ HMS's; then the
comparison is "same or more reclaim — who has better tail latency?"

**Expected (what supports the claim):** HMS has comparable/lower Peak RSS and Reclaimed pages
but **lower p99 frame time and fewer major faults** than Static-Aggressive. If Static-Aggressive
ties HMS on p99, the cross-layer claim is not supported and must be softened.

## Experiment 2 — Four-signal ablation (Table `tab:altsignals`)

**Goal:** show the *fused* $H_u$ beats single-signal triggers.

**Setup:** build four variants of HMS that differ **only** in the trigger predicate — footprint-only,
rate-only, PSI-only, full $H_u$ — keeping the Enforcer, page budget, and threshold-calibration
procedure identical. Run W1–W4, average the five columns.

**Expected ordering (from paper §4.2):** footprint-only → late (high $L_r$, worse tail on bursty
W1/W3); rate-only → over-reclaims (high reclaim vol. + misprediction on W2/W4); PSI-only → lags
everywhere; $H_u$ → best trade-off. Report the ordering; if it differs, revise the rationale text.

## Experiment 3 — Misprediction rate & hysteresis (Tables `tab:mispred`, `tab:hysteresis`)

**Log inside the Runtime Observer:** every time $H_u > \theta_2$, record `{timestamp, pid, H_u,
pages_reclaimed}` = one **θ₂ crossing**.

**Label a crossing a misprediction** if, within a window `W` (e.g., 2 s) *after* it, the
high-pressure condition it was meant to avert did **not** occur. Operationalize "high-pressure" as
any of: `/proc/pressure/memory` `some avg10` > X%, an LMKD kill, or a global low-memory event.
`misprediction_rate = mispredictions / θ₂_crossings`.

**Added latency per misprediction (ms)** = the $L_r$ of that (unnecessary) shrinker pass + any
zRAM decompress cost for pages re-touched shortly after (count reads on `/sys/block/zram0/mm_stat`
in the following window). **Δ p99 frame** = p99 with vs. without those events.

**Hysteresis table:** sweep `θ₂ − θ₁ ∈ {0.05, 0.10, 0.15, 0.20}` on one representative workload;
expect misprediction rate to fall as the band widens (with $L_r$ rising slightly as action is delayed).

## Experiment 4 — Reclaim–GC interaction (Table `tab:reclaimgc`)

**Goal:** prove lower $T_{gc}$ is real relief, not faults pushed into the GC window.

**Method:** from the ART trace, mark each GC window `[t_start, t_end]`. For each window that
follows a reclaim, count **major faults** (`/proc/<pid>/stat majflt` delta in-window) and
**page-ins** (zRAM reads / `pswpin` in-window). Average over W1–W4 for Baseline vs. HMS.

**Expected:** HMS shows **lower $T_{gc}$ *and* low post-reclaim faults** — i.e., the targeted,
inactive-page reclaim rarely intersects the collector's live young-gen set.

## Experiment 5 — Low-pressure control W5 (Table `tab:lowpressure`)

**Goal:** show HMS is inert when there is no genuine pressure (no blanket-reclaim bias).

**Workload W5:** light social-media scrolling + web browsing; system stays well under budget.
Report θ₂ crossings (expect ≈ 0), reclaim volume (≈ 0), foreground p99 frame, and FG latency Δ%
vs. baseline.

**Expected:** HMS ≈ Baseline; θ₂ crossings near zero and `|FG latency Δ|` within run-to-run noise.

---

## Reproducibility checklist (for the paper's artifact statement)
- Pin device model, SoC, RAM, Android build, kernel version, and all `vm.*`/`ro.lmk.*` values.
- Report N runs per (system × workload) with mean ± 95% CI (you already use two-tailed t-tests).
- Release the Perfetto configs, the θ₂-crossing/misprediction labeler script, and raw traces.

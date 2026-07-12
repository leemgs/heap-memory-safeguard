# HMS artifact tools

Runnable scripts to collect the data for the five outstanding experiments and to
populate the red `--` cells in the evaluation tables. Tested for
syntax/logic on synthetic inputs; they use real Android/Linux interfaces and are
meant to run against a rooted test device over `adb`.

## Files
- `perfetto_hms.cfg` — Perfetto trace config (ftrace vmscan/GC, process_stats, sys_stats).
- `sample_counters.sh` — on-device 1 Hz sampler → `rss.csv`, `vmstat.csv`, `zram.csv`, `psi.csv`.
- `run_experiment.sh` — host driver: trace + sample + run a workload + pull results.
- `compute_metrics.py` — computes peak RSS, major faults/min, reclaim volume, zRAM, PSI, p99 frame.
- `label_mispredictions.py` — labels θ₂ crossings as true-positive vs misprediction.
- `trace_queries.sql` — Trace Processor SQL for `L_r`, `T_gc`, post-reclaim faults in GC windows.

## One run, end to end
```bash
# 1) collect (repeat per system × workload, N times each)
./run_experiment.sh hms W1 com.example.camera 60 runs/hms_W1_01

# 2) counter-based columns
python3 compute_metrics.py runs/hms_W1_01

# 3) trace-based columns (L_r, T_gc, faults-in-GC)
trace_processor_shell -q trace_queries.sql runs/hms_W1_01/trace.perfetto-trace

# 4) misprediction table (needs the Observer's event log; see below)
python3 label_mispredictions.py \
    --events runs/hms_W1_01/hms_events.jsonl \
    --psi    runs/hms_W1_01/psi.csv \
    --lmkd   runs/hms_W1_01/lmkd.csv \
    --window-s 2.0 --psi-threshold 20.0
```

## What the HMS Observer must log (`hms_events.jsonl`)
Add one line per θ₂ crossing from the Runtime Observer you already have:
```json
{"ts_ns":<CLOCK_MONOTONIC ns>,"pid":..,"uid":..,"hu":0.83,"theta1":0.7,"theta2":0.8,
 "event":"theta2_cross","pages_reclaimed":512,"Lr_ms":3.2,"workload":"W1"}
```
Use the same clock as the trace (`CLOCK_MONOTONIC`) so timestamps align with PSI/LMKD.

## Mapping to the paper tables
| Table | Produced by |
|---|---|
| `tab:isolate` (Exp 1) | `compute_metrics.py` (RSS, faults, reclaim, p99) + `trace_queries.sql` (`L_r`,`T_gc`) |
| `tab:altsignals` (Exp 2) | same, run once per signal variant (footprint/rate/psi/H_u) |
| `tab:mispred`, `tab:hysteresis` (Exp 3) | `label_mispredictions.py` (sweep `--` for hysteresis by rebuilding with different θ bands) |
| `tab:reclaimgc` (Exp 4) | `trace_queries.sql` (faults-in-GC) + `compute_metrics.py` (`T_gc` cross-check) |
| `tab:lowpressure` (Exp 5) | `run_experiment.sh ... W5 ...` then `compute_metrics.py` + `label_mispredictions.py` (expect ~0 crossings) |

## Notes / caveats to adjust on your platform
- ART GC slice names vary; tune the `GLOB '*GC*'` filters in `trace_queries.sql`.
- `gfxinfo framestats` column order changes across Android versions; verify the
  `intended_vsync`/`frame_completed` indices in `compute_metrics.py::p99_frame_ms`.
- `pgsteal_*` in `/proc/vmstat` is summed across zones/nodes; that is intended.
- PSI sampling needs a PSI-enabled kernel; the `some avg10` threshold (default 20%)
  is a starting point — calibrate it against a known stall on your device.
- For statistical rigor, run N≥5 repetitions per cell and report mean ± 95% CI.

---

## Four-signal ablation build (`trigger_variants.c`, `Makefile`)
The ablation (Table `tab:altsignals`) needs four builds that differ ONLY in the
decision signal. `trigger_variants.c` isolates that one function; select the
signal at build time:
```bash
make objs        # builds hms_footprint.o hms_rate.o hms_psi.o hms_hu.o
make test        # standalone smoke test of the H_u variant
```
Fill the `read_*()` stubs with your existing Observer plumbing and link each
object against your real `enforcer.o`. Everything below the
"DO NOT CHANGE PER VARIANT" line stays identical across builds, which is what
makes the comparison fair. The variant also emits the `theta2_cross` JSONL line
consumed by `label_mispredictions.py`.

## CSV -> LaTeX tables (`make_tables.py`, `results/`)
`results/*.csv` are fill-in templates whose columns match the six evaluation
tables. Put your measured means in the cells (leave blank = renders as `\tbd`),
then generate a complete `tabular`:
```bash
# lower-is-better columns bolded by index; S_h (col 3) is higher-is-better
python3 make_tables.py results/isolate.csv    --out results/tab_isolate.tex    --bold-min "1,2,3,4,5,6"
python3 make_tables.py results/altsignals.csv --out results/tab_altsignals.tex --bold-min "1,2,4,5" --bold-max "3"
python3 make_tables.py results/mispred.csv    --out results/tab_mispred.tex
python3 make_tables.py results/hysteresis.csv --out results/tab_hysteresis.tex
python3 make_tables.py results/reclaimgc.csv  --out results/tab_reclaimgc.tex
python3 make_tables.py results/lowpressure.csv --out results/tab_lowpressure.tex
```
Then, in `065_evaluation.tex`, replace each skeleton `\begin{tabular}...\end{tabular}`
with a single line, keeping your `\caption`/`\label`:
```latex
\input{tools/results/tab_isolate.tex}
```
Notes: `--bold-min/--bold-max` take 1-based *data*-column indices (robust) or
exact header text; the best numeric value per selected column is bolded. The
generator emits a complete `tabular` (not partial rows) so the `\input` is safe
inside a float.

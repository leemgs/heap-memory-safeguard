# HMS (Heap Memory Safeguard) — Research Artifact (Simulation)

* Current name: **HMS** (Heap Memory Safeguard) — used throughout the paper.
* Former name: HMP (Heap Memory Protector). For import compatibility the Python
  package is still named `hmp` (e.g. `from hmp.controller import HMPController`);
  only the package path is historical, the system is HMS.

This repository provides a **self-contained simulation** and scripts to explore
the paper's controller logic:
- Parameter sensitivity plots (e.g., `fig9_W1_alpha_vs_Sh_3alpha.png`, `fig9_W2_theta1_vs_Lr.png`, `fig9_W3_theta2_vs_Sh.png`, `fig9_W4_theta2_vs_Lr.png`, `fig_param_sensitivity.png`)
- A summary metrics table (CSV) comparing **Baseline** vs **HMS** across workloads **W1–W4**: heap stability (Sₕ), reclaim latency (Lᵣ), GC pause (T_gc), peak RSS reduction, and energy overhead

> ⚠️ This is a **lightweight simulation** for policy exploration and ablation. It
> does **not** reproduce device measurements, modify an OS kernel, or modify a
> vendor runtime.

## Repo Layout

```
hmp-repro/
├─ hmp/
│  ├─ __init__.py
│  ├─ telemetry.py      # synthetic workloads (W1..W4)
│  ├─ tagging.py        # synthetic RSS-volatility proxy (not Arm MTE)
│  ├─ memcg.py          # memcg-like reclaim proxy
│  └─ controller.py     # HMS policy (α, θ₁, θ₂)
├─ scripts/
│  └─ run_experiments.py
├─ data/                # (optional) place raw/exported data here
├─ results/
│  ├─ figures/          # generated figures
│  └─ metrics/          # generated CSVs
├─ requirements.txt
├─ LICENSE.md
└─ README.md
```

## Quickstart

### 1) Create environment
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Reproduce results
This will generate **metrics CSV** and **all figures** under `results/`.

```bash
python scripts/run_experiments.py --alpha 0.35 --theta1 0.12 --theta2 0.18 --rss-limit 1024 --seed 7 --outdir results
```

Expected outputs:
- `results/metrics/summary.csv` — baseline vs HMS metrics for W1–W4
- `results/figures/fig9_W1_alpha_vs_Sh_3alpha.png`
- `results/figures/fig9_W2_theta1_vs_Lr.png`
- `results/figures/fig9_W3_theta2_vs_Sh.png`
- `results/figures/fig9_W4_theta2_vs_Lr.png`
- `results/figures/fig_param_sensitivity.png`

### 3) Interpreting metrics

- **Heap stability (Sₕ)**: `1 - std(rss)/mean(rss)` (higher is better).
- **Reclaim latency (Lᵣ)**: median of simulated memcg reclaim latency (ms) (lower is better).
- **GC pause (T_gc)**: median simulated pause time (ms) (lower is better).
- **Peak RSS reduction**: percent drop in max RSS with HMS vs baseline.
- **Energy overhead**: mean additional power from enforcement (W).

> The numeric values are synthetic model outputs. Use them for relative comparisons
> and sensitivity analyses, not as evidence of typical device behavior.

## Customizing parameters

You can sweep parameters to mirror the paper's **“Parameter Sensitivity”** section:

```bash
python scripts/run_experiments.py --alpha 0.55 --theta1 0.10 --theta2 0.22
```

- `alpha (α)`: weights allocation velocity in the utilization index **Hᵤ**.
- `theta1 (θ₁), theta2 (θ₂)`: enforcement thresholds; higher values delay enforcement.

### Threshold scale

The default `--theta1 0.12 --theta2 0.18` values are simulation parameters selected
for the synthetic traces' occupancy range. They are not device presets. Only the
model's relative behavior under parameter sweeps is evaluated; no transfer to a
physical memory tier is claimed.

## Reproducing named figures from the paper

This simulation writes files with the **same names** referenced in the manuscript so you can drop them into your LaTeX build:

- `fig9_W1_alpha_vs_Sh_3alpha.png`
- `fig9_W2_theta1_vs_Lr.png`
- `fig9_W3_theta2_vs_Sh.png`
- `fig9_W4_theta2_vs_Lr.png`
- `fig_param_sensitivity.png`

All figures are saved at 160 DPI. If your publisher requests different sizes, re-run with a different `dpi` by editing `scripts/run_experiments.py`.

## Data and determinism

- Workloads **W1–W4** are random but **seeded** for determinism (`--seed`).
- Use the same `--seed` to regenerate identical results.

## Citing / License

- License: **Apache-2.0** (see `LICENSE.md`).
- If you use or extend this artifact, please cite the associated paper and acknowledge this repository.

## FAQ

**Q: Does this run on Windows/macOS/Linux?**  
A: Yes, it’s pure Python + NumPy/Matplotlib.

**Q: Can I change the figure style/colors?**  
A: Yes—edit the plotting section in `scripts/run_experiments.py`. The defaults intentionally avoid style packs to keep environments minimal.

**Q: Where are the kernel patches?**  
A: This artifact is a **simulation-only** reproduction target—ideal for CI, classrooms, and ablations without device access.

---

_Artifact built on: 2025-10-12T10:59:07.545535Z_

## Kernel (Out-of-tree) Scaffold
- See `hmp/kernel/README-kernel.md` for building the optional kernel module (`hmp_kmod.ko`).

## User-space bridge to kernel (/dev/hmp_ctl)
- Optional char device exposed by the kernel scaffold for **live control & telemetry**.
- Examples:
  - `python -m hmp.bridge --watch`
  - `python -m hmp.bridge --set alpha_milli 350 --set theta1_milli 120`

# HMS (Heap Memory Safeguard) — Research Artifact (Simulation)

* Current name: **HMS** (Heap Memory Safeguard) — used throughout the paper.
* Former name: HMP (Heap Memory Protector). For import compatibility the Python
  package is still named `hmp` (e.g. `from hmp.controller import HMPController`);
  only the package path is historical, the system is HMS.

This repository provides a **self-contained simulation** and scripts to **reproduce the paper’s key results**:
- Parameter sensitivity plots (e.g., `fig9_W1_alpha_vs_Sh_3alpha.png`, `fig9_W2_theta1_vs_Lr.png`, `fig9_W3_theta2_vs_Sh.png`, `fig9_W4_theta2_vs_Lr.png`, `fig_param_sensitivity.png`)
- A summary metrics table (CSV) comparing **Baseline** vs **HMS** across workloads **W1–W4**: heap stability (Sₕ), reclaim latency (Lᵣ), GC pause (T_gc), peak RSS reduction, and energy overhead

> ⚠️ This is a **lightweight simulation** intended for artifact reproduction and ablation studies; it does **not** modify any OS kernel or vendor runtime. It encodes the control ideas (α, θ₁, θ₂) and produces deterministic figures/metrics without platform dependencies.

## Repo Layout

```
hmp-repro/
├─ hmp/
│  ├─ __init__.py
│  ├─ telemetry.py      # synthetic workloads (W1..W4)
│  ├─ tagging.py        # hardware tagging proxy
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

> The numeric values are **scaled** to match typical device behaviors and paper trends. Use them for **relative comparisons** and sensitivity analyses, not for device certification.

## Customizing parameters

You can sweep parameters to mirror the paper's **“Parameter Sensitivity”** section:

```bash
python scripts/run_experiments.py --alpha 0.55 --theta1 0.10 --theta2 0.22
```

- `alpha (α)`: weights allocation velocity in the utilization index **Hᵤ**.
- `theta1 (θ₁), theta2 (θ₂)`: enforcement thresholds; higher values delay enforcement.

### Note on the θ₁/θ₂ scale (simulation vs. paper presets)

The paper's device-class presets (Table *"Recommended presets"*) are calibrated for a
process running **near its memcg limit**, so Hᵤ operates close to 1 and the thresholds
are **α∈{0.35, 0.55}, (θ₁,θ₂)∈{(0.85,0.95), (0.80,0.90)}** for 8 GB / 12 GB devices.

This simulation deliberately keeps the synthetic workloads **well under** their
`rss-limit` (occupancy ≈ 0.15–0.35, so Hᵤ stays in roughly the same range). The default
`--theta1 0.12 --theta2 0.18` are the **internal-scale** equivalents that place the
observation/enforcement band inside that operating range; they are **not** the device
thresholds. Only the *relative* behavior (ordering and trends of Sₕ, Lᵣ, T_gc under
parameter sweeps) transfers to the paper — absolute values are scaled, as noted above.
To explore the controller near the device operating point instead, lower the limit so
occupancy approaches 1, e.g. `--rss-limit 320 --theta1 0.85 --theta2 0.95`.

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

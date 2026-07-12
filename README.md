# Heap Memory Safeguard (HMS)

**HMS** is an OS-level framework that co-locates runtime heap telemetry with
kernel-level memory reclamation under a single coordinated control loop, reducing
interactive-latency and memory-pressure stalls on mobile and embedded platforms.
It fuses resident footprint with allocation velocity into a heap-utilization index
($H_u$) to trigger *targeted* reclamation before pressure escalates — without any
application changes.

This repository contains the research paper and a reproducible simulation artifact.

## Repository layout

| Folder | Description |
|--------|-------------|
| [`paper/`](paper/) | LaTeX sources for the manuscript (ACM TECS format). Build entry point is `main.tex`, which produces `main.pdf`. Includes the figures, the `reference-data.bib` bibliography, the evaluation tables under `tools/results/`, and the data-collection/table-generation scripts in `tools/`. |
| [`code/`](code/) | Self-contained Python **simulation** that reproduces the paper's key trends (parameter-sensitivity figures and the Baseline-vs-HMS metrics summary for workloads W1–W4). It encodes the control ideas ($\alpha$, $\theta_1$, $\theta_2$) and does not modify any kernel or vendor runtime. See [`code/README.md`](code/README.md) for details. An out-of-tree kernel-module scaffold lives in `code/hmp/kernel/`. |

## Building the paper

```bash
cd paper
# with a LaTeX toolchain (acmart) or tectonic:
tectonic main.tex        # or: pdflatex main.tex && bibtex main && pdflatex ... (x2)
```

## Running the simulation

```bash
cd code
pip install -r requirements.txt
python scripts/run_experiments.py --alpha 0.35 --theta1 0.12 --theta2 0.18 \
    --rss-limit 1024 --seed 7 --outdir results
```

> Note: the simulation reproduces *relative* trends, not device-absolute values.
> See `code/README.md` for how its internal thresholds map to the paper's
> device-class presets.

## License

Apache-2.0 (see [`code/LICENSE.md`](code/LICENSE.md)).

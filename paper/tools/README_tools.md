# Device-measurement tools

These scripts are scaffolding for the future validation protocol in
[`../MEASUREMENT_GUIDE.md`](../MEASUREMENT_GUIDE.md). They are not the provenance
of the checked-in simulation figures and do not demonstrate that a phone experiment
was performed.

- `run_experiment.sh`: workload-run wrapper template
- `sample_counters.sh`: RSS/vmstat/PSI sampling template
- `perfetto_hms.cfg`: trace configuration template
- `trace_queries.sql`: candidate trace queries
- `label_mispredictions.py`: event-labeling helper
- `compute_metrics.py`: metric helper
- `make_tables.py`: table-generation helper

Before using outputs in a paper, commit immutable raw inputs, checksums,
device/build configuration, one row per run, exclusions, and the exact generation
command. Empty cells must remain empty; never replace missing measurements with
expected values.

# Device validation protocol

The checked-in HMS artifact is simulation-only. This document is a protocol for a
future Android implementation study; it is not evidence that the experiments have
already been run.

## Required implementation disclosure

Record the AOSP tag, ART commit, kernel/GKI/vendor commits, collector, heap limits,
zRAM, LMKD properties, MGLRU state, device/root status, changed files and LOC,
Binder/eventfd interfaces, permissions, and SELinux policy. Publish framework, ART,
kernel, build, workload-driver, and analysis patches.

## Required systems and devices

Compare Stock, tuned LMKD/PSI, direct `memory.reclaim`, equal-volume static reclaim,
a PSI daemon, DAMON/DAMOS, MGLRU tuning, footprint-only, rate-only, HMS without
native telemetry, and full HMS. Use at least four RAM tiers and two SoC vendors.

## Raw run schema

One row per `device × workload × system × run`:

```text
device,workload,system,run,seed,duration_s,peak_rss_mb,gc_p50_ms,
gc_p95_ms,gc_p99_ms,reclaim_p99_ms,frame_p99_ms,deadline_miss_ratio,
energy_j,reclaim_bytes,major_faults,refaults,app_kills
```

Archive the raw Perfetto trace, `hms_events.jsonl`, RSS, vmstat, PSI, thermal and
power samples, configuration, exclusions, and checksums for each row.

## Analysis

Preserve within-run pairing. Report every distribution, confidence interval,
effect size, multiple-comparison correction, excluded run, and outlier rule.
Use bootstrap or paired nonparametric inference for heavy-tailed latency unless
diagnostics justify a parametric model. Device and run replication must not be
pooled as independent observations.

## Stress and correctness

Include 6–24 hour mixed workloads, concurrent unstable processes, sustained
allocation, refault after reclaim, GC/reclaim overlap, zRAM thrashing, dynamic
limits, cgroup exit/offline races, energy, thermal throttling, writeback, inference
accuracy, camera correctness, texture reloads, AR tracking, launch regression,
background completion, kernel warnings, and deadlocks.

Do not populate manuscript tables until the raw inputs and generation command are
checked into a versioned release.

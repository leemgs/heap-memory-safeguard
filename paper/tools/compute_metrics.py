#!/usr/bin/env python3
"""compute_metrics.py — turn one run's sampled CSVs into table columns.

Computes: peak RSS (MB), major faults/min, reclaim volume (MB) and K-pages,
zRAM compression + reads, PSI pressure summary, and p99 frame time (from a
gfxinfo framestats dump). L_r and T_gc come from the Perfetto trace via
trace_queries.sql (see that file); this script covers the counter-based columns.

Usage:
  python3 compute_metrics.py <run_dir> [--frames gfxinfo_framestats.txt]
Prints a one-line JSON summary and a human-readable table.
"""
import argparse, csv, json, os, sys

def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

def fnum(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d

def peak_rss_mb(run):
    rows = read_csv(os.path.join(run, "rss.csv"))
    if not rows:
        return None
    return round(max(fnum(r["rss_kb"]) for r in rows) / 1024.0, 1)

def span_minutes(rows):
    if len(rows) < 2:
        return None
    t0 = fnum(rows[0]["ts_ns"]); t1 = fnum(rows[-1]["ts_ns"])
    return (t1 - t0) / 1e9 / 60.0 if t1 > t0 else None

def vmstat_deltas(run):
    rows = read_csv(os.path.join(run, "vmstat.csv"))
    if len(rows) < 2:
        return {}
    mins = span_minutes(rows) or None
    def delta(col):
        return fnum(rows[-1][col]) - fnum(rows[0][col])
    d = {
        "major_faults_per_min": round(delta("pgmajfault") / mins, 1) if mins else None,
        "reclaim_kpages": round(delta("pgsteal") / 1000.0, 1),
        "reclaim_volume_mb": round(delta("pgsteal") * 4096 / 1024 / 1024, 1),  # pages*4KiB
        "swap_in_pages": int(delta("pswpin")),
        "swap_out_pages": int(delta("pswpout")),
    }
    return d

def zram_summary(run):
    rows = read_csv(os.path.join(run, "zram.csv"))
    if not rows:
        return {}
    last = rows[-1]
    orig = fnum(last["orig_data_size"]); compr = fnum(last["compr_data_size"])
    ratio = round(orig / compr, 2) if compr else None
    reads = int(fnum(rows[-1]["num_reads"]) - fnum(rows[0]["num_reads"]))
    return {"zram_orig_mb": round(orig/1024/1024, 1),
            "zram_compr_mb": round(compr/1024/1024, 1),
            "zram_ratio": ratio, "zram_reads": reads}

def psi_summary(run):
    rows = read_csv(os.path.join(run, "psi.csv"))
    if not rows:
        return {}
    some = [fnum(r["some_avg10"]) for r in rows]
    return {"psi_some_avg10_mean": round(sum(some)/len(some), 2),
            "psi_some_avg10_max": round(max(some), 2)}

def p99_frame_ms(run, frames_file):
    """Parse `dumpsys gfxinfo <pkg> framestats` for per-frame total time.
    framestats rows are CSV with nanosecond timestamps; frame time =
    (FRAME_COMPLETED - INTENDED_VSYNC). Column layout can vary by Android
    version; adjust indices if needed."""
    path = os.path.join(run, frames_file)
    if not os.path.exists(path):
        return None
    durations = []
    for line in open(path):
        line = line.strip()
        if not line or not line[0].isdigit() or "," not in line:
            continue
        parts = line.split(",")
        try:
            vals = [int(p) for p in parts if p.strip().lstrip("-").isdigit()]
            # INTENDED_VSYNC is col 1, FRAME_COMPLETED is the last large ns value.
            intended = vals[1]; completed = vals[-1]
            ms = (completed - intended) / 1e6
            if 0 < ms < 1000:
                durations.append(ms)
        except (IndexError, ValueError):
            continue
    if not durations:
        return None
    durations.sort()
    idx = max(0, int(round(0.99 * (len(durations) - 1))))
    return round(durations[idx], 1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--frames", default="gfxinfo_framestats.txt")
    a = ap.parse_args()

    out = {"run": os.path.basename(a.run_dir.rstrip("/"))}
    out["peak_rss_mb"] = peak_rss_mb(a.run_dir)
    out.update(vmstat_deltas(a.run_dir))
    out.update(zram_summary(a.run_dir))
    out.update(psi_summary(a.run_dir))
    out["p99_frame_ms"] = p99_frame_ms(a.run_dir, a.frames)
    out["note"] = "L_r and T_gc: run trace_queries.sql on trace.perfetto-trace"

    print(json.dumps(out))
    print("\n--- metrics ---", file=sys.stderr)
    for k, v in out.items():
        print(f"{k:24s} {v}", file=sys.stderr)

if __name__ == "__main__":
    main()

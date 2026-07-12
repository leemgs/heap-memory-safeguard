#!/usr/bin/env python3
"""label_mispredictions.py — classify HMS theta2 crossings as true or mispredicted.

A theta2 crossing is a MISPREDICTION if, within a window W after it, the
high-pressure condition it was meant to avert did NOT occur. High pressure is
defined as PSI memory `some avg10` exceeding a threshold, OR an LMKD/OOM kill.

Inputs
------
hms_events.jsonl : one JSON object per line emitted by the HMS Runtime Observer:
    {"ts_ns":..., "pid":..., "uid":..., "hu":0.83, "theta1":0.7, "theta2":0.8,
     "event":"theta2_cross", "pages_reclaimed":512, "Lr_ms":3.2,
     "workload":"W1"}      # workload optional
psi.csv          : ts_ns,some_avg10,some_total,full_avg10,full_total  (from sampler)
lmkd.csv         : ts_ns,pid,reason   (optional; from logcat 'lmkd' / oom mark_victim)

Usage
-----
  python3 label_mispredictions.py --events hms_events.jsonl --psi psi.csv \
      [--lmkd lmkd.csv] [--window-s 2.0] [--psi-threshold 20.0]

Outputs
-------
  labeled.csv (per-event) and a per-workload summary printed to stdout:
    theta2 crossings, mispredictions, misprediction rate (%),
    mean added latency per misprediction (ms) = mean Lr_ms of mispredicted events.
"""
import argparse, csv, json, sys
from collections import defaultdict

def load_events(path):
    ev = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        if o.get("event") == "theta2_cross":
            ev.append(o)
    return ev

def load_psi(path):
    rows = []
    if not path:
        return rows
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append((int(float(r["ts_ns"])), float(r["some_avg10"])))
            except (KeyError, ValueError):
                continue
    rows.sort()
    return rows

def load_kills(path):
    rows = []
    if not path:
        return rows
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append(int(float(r["ts_ns"])))
            except (KeyError, ValueError):
                continue
    rows.sort()
    return rows

def high_pressure_in_window(t0, t1, psi, kills, thr):
    # PSI exceeded?
    for ts, some in psi:
        if ts < t0:
            continue
        if ts > t1:
            break
        if some >= thr:
            return True
    # any kill in window?
    for ts in kills:
        if t0 <= ts <= t1:
            return True
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True)
    ap.add_argument("--psi", default=None)
    ap.add_argument("--lmkd", default=None)
    ap.add_argument("--window-s", type=float, default=2.0)
    ap.add_argument("--psi-threshold", type=float, default=20.0,
                    help="PSI memory some avg10 %% that counts as high pressure")
    ap.add_argument("--out", default="labeled.csv")
    a = ap.parse_args()

    events = load_events(a.events)
    psi = load_psi(a.psi)
    kills = load_kills(a.lmkd)
    win_ns = int(a.window_s * 1e9)

    per_wl = defaultdict(lambda: {"cross": 0, "mispred": 0, "lr_sum": 0.0})
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_ns", "workload", "pid", "hu", "pages_reclaimed",
                    "Lr_ms", "label"])
        for e in events:
            t0 = int(e["ts_ns"]); t1 = t0 + win_ns
            averted = high_pressure_in_window(t0, t1, psi, kills, a.psi_threshold)
            label = "true_positive" if averted else "misprediction"
            wl = e.get("workload", "all")
            s = per_wl[wl]
            s["cross"] += 1
            if label == "misprediction":
                s["mispred"] += 1
                s["lr_sum"] += float(e.get("Lr_ms", 0.0))
            w.writerow([t0, wl, e.get("pid"), e.get("hu"),
                        e.get("pages_reclaimed"), e.get("Lr_ms"), label])

    # summary
    print(f"{'WL':<6}{'cross':>8}{'mispred':>9}{'rate(%)':>9}{'added_lat_ms':>14}")
    tot = {"cross": 0, "mispred": 0, "lr_sum": 0.0}
    for wl in sorted(per_wl):
        s = per_wl[wl]
        rate = 100.0 * s["mispred"] / s["cross"] if s["cross"] else 0.0
        added = s["lr_sum"] / s["mispred"] if s["mispred"] else 0.0
        print(f"{wl:<6}{s['cross']:>8}{s['mispred']:>9}{rate:>9.1f}{added:>14.2f}")
        for k in tot:
            tot[k] += s[k]
    rate = 100.0 * tot["mispred"] / tot["cross"] if tot["cross"] else 0.0
    added = tot["lr_sum"] / tot["mispred"] if tot["mispred"] else 0.0
    print(f"{'ALL':<6}{tot['cross']:>8}{tot['mispred']:>9}{rate:>9.1f}{added:>14.2f}")
    print(f"\nwrote {a.out}", file=sys.stderr)

if __name__ == "__main__":
    main()

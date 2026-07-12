#!/usr/bin/env bash
# run_experiment.sh — host-side driver for one HMS experiment run.
# Starts a Perfetto trace + on-device counter sampler, runs a workload, pulls results.
#
# Usage:
#   ./run_experiment.sh <system> <workload> <target_pkg> <duration_s> <outdir>
#     system    : baseline | static-aggressive | hms | footprint | rate | psi
#     workload  : W1..W5
#     target_pkg: the app package under test (e.g., com.example.camera)
#
# Example:
#   ./run_experiment.sh hms W1 com.example.camera 60 runs/hms_W1_01
#
# NOTE: fill in the workload launch/drive commands in start_workload() below.
set -euo pipefail

SYS="${1:?system}"; WL="${2:?workload}"; PKG="${3:?package}"
DUR="${4:-60}"; OUT="${5:?outdir}"
DEV_TMP=/data/local/tmp/hms_run
mkdir -p "$OUT"

adb shell mkdir -p "$DEV_TMP"
adb push perfetto_hms.cfg "$DEV_TMP/perfetto_hms.cfg" >/dev/null
adb push sample_counters.sh "$DEV_TMP/sample_counters.sh" >/dev/null

start_workload() {
  # TODO(author): implement per-workload driving. Examples:
  case "$WL" in
    W1) adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null ;; # camera pipeline
    W2) adb shell am start -n "$PKG/.MainActivity" >/dev/null ;;                        # game
    W3) adb shell am start -n "$PKG/.InferenceActivity" >/dev/null ;;                   # on-device inference
    W4) adb shell am start -n "$PKG/.StressActivity" >/dev/null ;;                      # multitasking
    W5) adb shell am start -n "$PKG/.BrowseActivity" >/dev/null ;;                      # low-pressure control
    *)  echo "unknown workload $WL"; exit 1 ;;
  esac
  # TODO(author): add scripted UI interaction (e.g., UiAutomator / monkey seed) here.
}

TARGET_PID=$(adb shell pidof "$PKG" | tr -d '\r' || true)
[ -n "$TARGET_PID" ] || { echo "launch $PKG first so pidof works"; adb shell am start "$PKG" || true; sleep 3; TARGET_PID=$(adb shell pidof "$PKG" | tr -d '\r'); }

# reset gfxinfo so framestats covers only this run
adb shell dumpsys gfxinfo "$PKG" reset >/dev/null 2>&1 || true

# start counter sampler (background, on device)
adb shell "sh $DEV_TMP/sample_counters.sh $TARGET_PID $DUR $DEV_TMP" &
SAMPLER=$!

# start perfetto trace (background, on device)
adb shell "cat $DEV_TMP/perfetto_hms.cfg | perfetto -c - --txt -o $DEV_TMP/trace.perfetto-trace" &
TRACER=$!

start_workload
sleep "$DUR"

wait "$SAMPLER" || true
wait "$TRACER"  || true

# capture frame stats + a meminfo snapshot
adb shell dumpsys gfxinfo "$PKG" framestats > "$OUT/gfxinfo_framestats.txt" 2>/dev/null || true
adb shell dumpsys meminfo "$PKG"             > "$OUT/meminfo.txt"            2>/dev/null || true

# pull everything
adb pull "$DEV_TMP/trace.perfetto-trace" "$OUT/" >/dev/null
for f in rss.csv vmstat.csv zram.csv psi.csv; do
  adb pull "$DEV_TMP/$f" "$OUT/" >/dev/null 2>&1 || true
done

echo "$SYS/$WL run complete -> $OUT"
echo "next: python3 compute_metrics.py $OUT ; python3 label_mispredictions.py ..."

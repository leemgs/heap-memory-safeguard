#!/system/bin/sh
# sample_counters.sh — 1 Hz sampler for HMS experiments.
# Run ON the device (adb shell) alongside a Perfetto trace. It samples the
# counters that are easier to read from /proc and /sys than from the trace.
#
# Usage (on device):
#   sh sample_counters.sh <target_pid> <duration_s> <outdir>
# Example:
#   sh sample_counters.sh 4321 60 /data/local/tmp/hms_run
#
# Output CSVs (in <outdir>):
#   rss.csv    ts_ns,pid,rss_kb
#   vmstat.csv ts_ns,pgmajfault,pgsteal,pgscan,pswpin,pswpout
#   zram.csv   ts_ns,orig_data_size,compr_data_size,mem_used_total,num_reads,num_writes
#   psi.csv    ts_ns,some_avg10,some_total,full_avg10,full_total

PID="$1"; DUR="${2:-60}"; OUT="${3:-/data/local/tmp/hms_run}"
mkdir -p "$OUT"

echo "ts_ns,pid,rss_kb" > "$OUT/rss.csv"
echo "ts_ns,pgmajfault,pgsteal,pgscan,pswpin,pswpout" > "$OUT/vmstat.csv"
echo "ts_ns,orig_data_size,compr_data_size,mem_used_total,num_reads,num_writes" > "$OUT/zram.csv"
echo "ts_ns,some_avg10,some_total,full_avg10,full_total" > "$OUT/psi.csv"

now_ns() { date +%s%N; }

end=$(( $(date +%s) + DUR ))
while [ "$(date +%s)" -lt "$end" ]; do
  TS=$(now_ns)

  # --- RSS of the target process (sum of native helpers can be added by PID list) ---
  if [ -r "/proc/$PID/smaps_rollup" ]; then
    RSS=$(awk '/^Rss:/ {print $2; exit}' "/proc/$PID/smaps_rollup")
    echo "$TS,$PID,${RSS:-0}" >> "$OUT/rss.csv"
  fi

  # --- Global vmstat counters (pages) ---
  PGMAJ=$(awk '/^pgmajfault /{print $2}' /proc/vmstat)
  PGSTEAL=$(awk '/^pgsteal_/{s+=$2} END{print s+0}' /proc/vmstat)
  PGSCAN=$(awk '/^pgscan_/{s+=$2} END{print s+0}' /proc/vmstat)
  PSWPIN=$(awk '/^pswpin /{print $2}' /proc/vmstat)
  PSWPOUT=$(awk '/^pswpout /{print $2}' /proc/vmstat)
  echo "$TS,${PGMAJ:-0},${PGSTEAL:-0},${PGSCAN:-0},${PSWPIN:-0},${PSWPOUT:-0}" >> "$OUT/vmstat.csv"

  # --- zRAM stats (mm_stat: orig compr mem_used ... ; stat: reads writes) ---
  if [ -r /sys/block/zram0/mm_stat ]; then
    set -- $(cat /sys/block/zram0/mm_stat)
    ORIG=$1; COMPR=$2; MEMUSED=$3
    RD=$(awk '{print $1}' /sys/block/zram0/stat 2>/dev/null)
    WR=$(awk '{print $5}' /sys/block/zram0/stat 2>/dev/null)
    echo "$TS,${ORIG:-0},${COMPR:-0},${MEMUSED:-0},${RD:-0},${WR:-0}" >> "$OUT/zram.csv"
  fi

  # --- PSI memory pressure ---
  if [ -r /proc/pressure/memory ]; then
    SOME=$(awk '/^some/{print}' /proc/pressure/memory)
    FULL=$(awk '/^full/{print}' /proc/pressure/memory)
    SA=$(echo "$SOME" | sed -n 's/.*avg10=\([0-9.]*\).*/\1/p')
    ST=$(echo "$SOME" | sed -n 's/.*total=\([0-9]*\).*/\1/p')
    FA=$(echo "$FULL" | sed -n 's/.*avg10=\([0-9.]*\).*/\1/p')
    FT=$(echo "$FULL" | sed -n 's/.*total=\([0-9]*\).*/\1/p')
    echo "$TS,${SA:-0},${ST:-0},${FA:-0},${FT:-0}" >> "$OUT/psi.csv"
  fi

  sleep 1
done
echo "sampling done -> $OUT"

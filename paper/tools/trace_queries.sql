-- trace_queries.sql — run against a Perfetto trace with the Trace Processor:
--   trace_processor_shell -q trace_queries.sql trace.perfetto-trace
-- or via the Python API: from perfetto.trace_processor import TraceProcessor
--
-- Produces the trace-derived columns: L_r (reclaim latency), T_gc (GC pause),
-- and post-reclaim major faults during GC windows.

-- ============================================================
-- L_r : direct-reclaim episode duration (ms)
-- Pairs mm_vmscan_direct_reclaim_begin/end via the slice/instant tables.
-- On most builds these appear as instant ftrace events; if your build emits
-- them as slices, use dur directly from the slice table instead.
-- ============================================================
DROP VIEW IF EXISTS reclaim_begin;
CREATE VIEW reclaim_begin AS
SELECT ts, ROW_NUMBER() OVER (ORDER BY ts) AS n
FROM slice WHERE name GLOB '*mm_vmscan_direct_reclaim_begin*';

DROP VIEW IF EXISTS reclaim_end;
CREATE VIEW reclaim_end AS
SELECT ts, ROW_NUMBER() OVER (ORDER BY ts) AS n
FROM slice WHERE name GLOB '*mm_vmscan_direct_reclaim_end*';

SELECT 'L_r_ms_mean' AS metric,
       ROUND(AVG((e.ts - b.ts) / 1e6), 3) AS value
FROM reclaim_begin b JOIN reclaim_end e USING (n)
WHERE e.ts > b.ts;

-- ============================================================
-- T_gc : ART garbage-collection pause (ms)
-- ART emits GC slices under the 'dalvik' atrace category. Pause slices are
-- typically named like 'GC: ... paused' / 'suspend' / 'CollectorTransition'.
-- Adjust the GLOB to match your platform's GC slice names if needed.
-- ============================================================
SELECT 'T_gc_ms_mean' AS metric,
       ROUND(AVG(dur / 1e6), 3) AS value
FROM slice
WHERE name GLOB '*GC*'          -- ART GC slices
  AND dur > 0;

-- Per-GC pause distribution (optional, for p50/p99 of pauses):
-- SELECT ROUND(dur/1e6,3) AS gc_pause_ms FROM slice
-- WHERE name GLOB '*GC*' AND dur>0 ORDER BY dur;

-- ============================================================
-- Post-reclaim major faults during GC windows
-- Counts rss_stat/major-fault activity that falls inside a GC slice that
-- itself follows a reclaim episode. Requires kmem/rss_stat or a majflt
-- counter in the trace; otherwise compute from /proc majflt deltas offline.
-- ============================================================
DROP VIEW IF EXISTS gc_windows;
CREATE VIEW gc_windows AS
SELECT ts AS gc_start, ts + dur AS gc_end
FROM slice WHERE name GLOB '*GC*' AND dur > 0;

-- Number of GC windows that begin within 200 ms after a reclaim end:
SELECT 'gc_after_reclaim_count' AS metric, COUNT(*) AS value
FROM gc_windows g
WHERE EXISTS (
  SELECT 1 FROM reclaim_end e
  WHERE g.gc_start >= e.ts AND g.gc_start <= e.ts + 200*1e6
);

-- Fault-like events inside those GC windows (name GLOB adjust per build):
SELECT 'faults_in_gc_windows' AS metric, COUNT(*) AS value
FROM slice s JOIN gc_windows g
  ON s.ts >= g.gc_start AND s.ts <= g.gc_end
WHERE s.name GLOB '*fault*' OR s.name GLOB '*pagein*';

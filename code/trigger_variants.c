/* trigger_variants.c — HMS decision-signal skeleton for the four-signal ablation.
 *
 * The ablation (Table tab:altsignals) requires four builds that differ ONLY in
 * the decision signal, with the Enforcer, page budget, hysteresis, and
 * calibration procedure held fixed. Select the signal at build time:
 *
 *   gcc -DHMS_SIGNAL=HMS_FOOTPRINT -Wall -c trigger_variants.c -o hms_footprint.o
 *   gcc -DHMS_SIGNAL=HMS_RATE      -Wall -c trigger_variants.c -o hms_rate.o
 *   gcc -DHMS_SIGNAL=HMS_PSI       -Wall -c trigger_variants.c -o hms_psi.o
 *   gcc -DHMS_SIGNAL=HMS_HU        -Wall -c trigger_variants.c -o hms_hu.o
 *
 * Fill the read_*() stubs with your existing Observer plumbing (smaps_rollup,
 * ART/heapprofd allocation counters, memcg limit, /proc/pressure/memory).
 * Everything below the "DO NOT CHANGE PER VARIANT" line must stay identical
 * across the four builds so the comparison is fair.
 */
#include <stdio.h>
#include <stdint.h>
#include <sys/types.h>

/* ---- signal selector ---- */
#define HMS_FOOTPRINT 1
#define HMS_RATE      2
#define HMS_PSI       3
#define HMS_HU        4
#ifndef HMS_SIGNAL
#define HMS_SIGNAL HMS_HU
#endif

/* ---- fixed control parameters (identical across variants) ---- */
static const double ALPHA      = 0.35;   /* foreground; 0.55 for background   */
static const double THETA1     = 0.70;   /* "unstable" watch threshold        */
static const double THETA2     = 0.80;   /* enforcement threshold             */
static const double PSI_THETA  = 20.0;   /* PSI-only: calibrated some.avg10 %% */
static const uint64_t PAGE_BUDGET = 4096;/* per-invocation reclaim cap (pages)*/

/* ---- per-process sample (fill from your platform) ---- */
typedef struct {
    pid_t  pid;
    int    uid;
    double rss;             /* resident set (bytes)              */
    double rlimit;          /* memcg limit for this uid (bytes)  */
    double arate;           /* allocation velocity (bytes/s)     */
    double amax;            /* normalization constant (bytes/s)  */
    double psi_some_avg10;  /* /proc/pressure/memory some avg10  */
} hms_sample;

/* ===================== platform read stubs (TODO) ===================== */
static double read_rss(pid_t pid)           { (void)pid; return 0.0; } /* /proc/<pid>/smaps_rollup Rss */
static double read_rlimit(int uid)          { (void)uid; return 1.0; } /* memcg memory.max            */
static double read_arate(pid_t pid)         { (void)pid; return 0.0; } /* ART/heapprofd delta/interval*/
static double read_amax(void)               { return 1.0; }           /* device-calibrated constant  */
static double read_psi_some_avg10(void)     { return 0.0; }           /* /proc/pressure/memory       */

/* ===================== enforcer + logging (fixed) ===================== */
/* Returns measured reclaim latency in ms (timestamp ioctl-entry..pass-done). */
extern double enforcer_reclaim(pid_t pid, int uid, uint64_t page_budget);
/* Emit one JSONL line for label_mispredictions.py. */
static void log_theta2_cross(const hms_sample *s, double hu, uint64_t pages, double lr_ms)
{
    printf("{\"ts_ns\":%lld,\"pid\":%d,\"uid\":%d,\"hu\":%.4f,"
           "\"theta1\":%.3f,\"theta2\":%.3f,\"event\":\"theta2_cross\","
           "\"pages_reclaimed\":%llu,\"Lr_ms\":%.3f}\n",
           (long long)0 /* TODO: CLOCK_MONOTONIC ns */, s->pid, s->uid,
           hu, THETA1, THETA2, (unsigned long long)pages, lr_ms);
}

/* ===================== DO NOT CHANGE PER VARIANT ===================== */
/* The ONLY thing that differs between the four builds is this function. */
static double hms_signal(const hms_sample *s)
{
#if   HMS_SIGNAL == HMS_FOOTPRINT
    return s->rss / s->rlimit;                              /* level only     */
#elif HMS_SIGNAL == HMS_RATE
    return s->arate / s->amax;                              /* velocity only  */
#elif HMS_SIGNAL == HMS_PSI
    return s->psi_some_avg10 / 100.0;                       /* kernel pressure*/
#else /* HMS_HU */
    return s->rss / s->rlimit + ALPHA * (s->arate / s->amax); /* level+velocity */
#endif
}

/* Enforcement decision. Hysteresis and budget are identical across variants;
 * PSI-only uses its separately calibrated threshold (documented in the paper). */
static int hms_should_enforce(double signal, const hms_sample *s)
{
#if HMS_SIGNAL == HMS_PSI
    (void)signal;
    return s->psi_some_avg10 >= PSI_THETA;
#else
    (void)s;
    return signal > THETA2;
#endif
}

/* One control cycle over one process (call at 1 Hz from your main loop). */
void hms_cycle_once(hms_sample *s)
{
    s->rss    = read_rss(s->pid);
    s->rlimit = read_rlimit(s->uid);
    s->arate  = read_arate(s->pid);
    s->amax   = read_amax();
    s->psi_some_avg10 = read_psi_some_avg10();

    double x = hms_signal(s);

    /* θ1 watch (soft) — same for all variants */
    int unstable = (x > THETA1);
    if (!unstable)
        return;

    if (hms_should_enforce(x, s)) {
        double lr_ms = enforcer_reclaim(s->pid, s->uid, PAGE_BUDGET);
        log_theta2_cross(s, x, PAGE_BUDGET, lr_ms);
    }
}

#ifdef HMS_STANDALONE_TEST
/* Compile a runnable smoke test:
 *   gcc -DHMS_STANDALONE_TEST -DHMS_SIGNAL=HMS_HU trigger_variants.c enforcer_stub.c -o t && ./t
 */
double enforcer_reclaim(pid_t pid, int uid, uint64_t b){(void)pid;(void)uid;(void)b;return 3.14;}
int main(void){ hms_sample s = {.pid=4321,.uid=10123}; hms_cycle_once(&s); return 0; }
#endif

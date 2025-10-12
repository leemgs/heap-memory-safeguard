/* SPDX-License-Identifier: Apache-2.0 */
/* Public-facing minimal kernel <-> userspace knob definitions for HMP */
#ifndef _HMP_KAPI_H
#define _HMP_KAPI_H

#include <linux/types.h>

struct hmp_params {
	/* utilization weight and thresholds */
	u32 alpha_milli;   /* e.g., 350 => 0.35 */
	u32 theta1_milli;  /* e.g., 120 => 0.12 */
	u32 theta2_milli;  /* e.g., 180 => 0.18 */

	/* rss limit in MB for normalization */
	u32 rss_limit_mb;
} __attribute__((packed));

struct hmp_stats {
	/* moving-window volatility proxy (x1000) */
	u32 unstable_milli;
	/* enforcement level (0..100) */
	u32 enforce_pct;
	/* reclaim latency proxy (ms) */
	u32 lr_ms;
	/* gc pause proxy (ms) */
	u32 tgc_ms;
	/* energy overhead proxy (mW) */
	u32 energy_mw;
} __attribute__((packed));

#endif /* _HMP_KAPI_H */

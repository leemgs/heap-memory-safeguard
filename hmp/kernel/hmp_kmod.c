\
/* SPDX-License-Identifier: Apache-2.0 */
/*
 * HMP kernel module (research scaffold)
 *
 * This out-of-tree module demonstrates:
 *  - sysfs knobs under /sys/kernel/hmp/{alpha,theta1,theta2,rss_limit,stats}
 *  - a periodic sampler that computes simple proxies for
 *    - utilization index Hu ~= rss/limit + alpha * alloc_velocity_norm
 *    - enforcement levels gated by theta1/theta2
 *  - a 'rate limiter' multiplier (not applied to real allocators here)
 *
 * NOTE: This is a minimal, portable example intended for artifact reproduction.
 *       It does NOT hook into real memcg reclaim or MTE. Integrations would
 *       require in-tree patches or vendor hooks.
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/jiffies.h>
#include <linux/workqueue.h>
#include <linux/mutex.h>
#include <linux/mm.h>
#include <linux/mmzone.h>
#include <linux/vmstat.h>
#include <linux/version.h>
#include <linux/sched.h>
#include <linux/delay.h>
#include <linux/slab.h>
#include <linux/miscdevice.h>
#include <linux/poll.h>
#include <linux/cred.h>
#include "hmp_kapi.h"

#define DRV_NAME "hmp_kmod"

static struct kobject *hmp_kobj;
static struct delayed_work hmp_work;
static DEFINE_MUTEX(hmp_lock);

/* ------------- /dev/hmp_ctl (misc char device) ------------- */
#define HMP_CTL_NAME "hmp_ctl"

static ssize_t hmp_ctl_read(struct file *filp, char __user *ubuf, size_t len, loff_t *ppos)
{
	/* Return one JSON snapshot per read from offset 0; then EOF. */
	char buf[512];
	int n;
	struct hmp_stats s;
	struct hmp_params p;

	if (*ppos != 0)
		return 0;

	mutex_lock(&hmp_lock);
	s = g_stats;
	p = g_params;
	mutex_unlock(&hmp_lock);

	n = scnprintf(buf, sizeof(buf),
		"{\"alpha_milli\":%u,\"theta1_milli\":%u,\"theta2_milli\":%u,"
		"\"rss_limit_mb\":%u,"
		"\"unstable_milli\":%u,\"psi_avg10_milli\":%u,"
		"\"memcg_current_mb\":%u,\"memcg_max_mb\":%u,"
		"\"enforce_pct\":%u,\"lr_ms\":%u,\"tgc_ms\":%u,\"energy_mw\":%u}\n",
		p.alpha_milli, p.theta1_milli, p.theta2_milli, p.rss_limit_mb,
		s.unstable_milli, psi_avg10_milli_cached, memcg_current_mb_cached, memcg_max_mb_cached,
		s.enforce_pct, s.lr_ms, s.tgc_ms, s.energy_mw);

	if (n > len) n = len;
	if (copy_to_user(ubuf, buf, n))
		return -EFAULT;
	*ppos += n;
	return n;
}

static u32 parse_kv_u32(const char *k, const char *line)
{
	const char *p = strstr(line, k);
	if (!p) return (u32)-1;
	p += strlen(k);
	if (*p != '=') return (u32)-1;
	p++;
	return (u32)simple_strtoul(p, NULL, 0);
}

static ssize_t hmp_ctl_write(struct file *filp, const char __user *ubuf, size_t len, loff_t *ppos)
{
	char kbuf[256];
	size_t n = len > sizeof(kbuf)-1 ? sizeof(kbuf)-1 : len;

	if (copy_from_user(kbuf, ubuf, n))
		return -EFAULT;
	kbuf[n] = '\0';

	/* Accept simple forms (one per write):
	 *   alpha_milli=350
	 *   theta1_milli=120
	 *   theta2_milli=180
	 *   rss_limit_mb=2048
	 */
	mutex_lock(&hmp_lock);
	do {
		u32 v;
		if ((v = parse_kv_u32("alpha_milli", kbuf)) != (u32)-1) {
			g_params.alpha_milli = clamp_u32(v, 0, 2000); break;
		}
		if ((v = parse_kv_u32("theta1_milli", kbuf)) != (u32)-1) {
			g_params.theta1_milli = clamp_u32(v, 0, 5000); break;
		}
		if ((v = parse_kv_u32("theta2_milli", kbuf)) != (u32)-1) {
			g_params.theta2_milli = clamp_u32(v, 0, 5000); break;
		}
		if ((v = parse_kv_u32("rss_limit_mb", kbuf)) != (u32)-1) {
			g_params.rss_limit_mb = clamp_u32(v, 128, 65536); break;
		}
	} while (0);
	mutex_unlock(&hmp_lock);

	return len;
}

static const struct file_operations hmp_ctl_fops = {
	.owner = THIS_MODULE,
	.read  = hmp_ctl_read,
	.write = hmp_ctl_write,
	.llseek = no_llseek,
};

static struct miscdevice hmp_misc = {
	.minor = MISC_DYNAMIC_MINOR,
	.name  = HMP_CTL_NAME,
	.fops  = &hmp_ctl_fops,
	.mode  = 0660, /* root + group writable; adjust via udev rules */
};


/* Parameters (milli for fixed-point) */
static struct hmp_params g_params = {
	.alpha_milli = 350,
	.theta1_milli = 120,
	.theta2_milli = 180,
	.rss_limit_mb = 1024,
};

/* Stats */
static struct hmp_stats g_stats;

/* Simple ring buffer to estimate volatility */
#define RING_MAX 128
static unsigned long rss_ring[RING_MAX];
static unsigned int ring_head;
static unsigned int ring_count;

/* Helpers */
static unsigned long get_estimated_rss_mb(void)
{
	/* Very rough global memory pressure proxy from vm stats */
	unsigned long totalram, freeram, cached;
	struct sysinfo i;

	si_meminfo(&i);
	totalram = (i.totalram * i.mem_unit) >> 20; /* MB */
	freeram  = (i.freeram  * i.mem_unit) >> 20; /* MB */

	/* Try to estimate cached pages (if available) */
#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,14,0)
	cached = global_node_page_state(NR_FILE_PAGES) >> (20 - PAGE_SHIFT);
#else
	cached = 0;
#endif
	/* naive: pretend rss ~= total - free - cached */
	if (totalram > freeram + cached)
		return totalram - freeram - cached;
	return totalram > freeram ? totalram - freeram : totalram;
}

static u32 clamp_u32(u32 v, u32 lo, u32 hi)
{
	if (v < lo) return lo;
	if (v > hi) return hi;
	return v;
}

static void ring_push(unsigned long v)
{
	rss_ring[ring_head] = v;
	ring_head = (ring_head + 1) % RING_MAX;
	if (ring_count < RING_MAX)
		ring_count++;
}

static u32 ring_volatility_milli(void)
{
	if (ring_count < 8)
		return 0;
	/* compute mean & stddev of ring (MB), return (std/mean)*1000 */
	unsigned int i;
	unsigned int n = ring_count;
	unsigned long sum = 0;
	for (i = 0; i < n; i++) sum += rss_ring[i];

	if (sum == 0) return 0;
	/* mean in fixed-point milli MB to stabilize */
	u64 mean_m = (1000ULL * sum) / n;

	u64 var_acc = 0;
	for (i = 0; i < n; i++) {
		long diff_m = (long)(1000UL * rss_ring[i]) - (long)mean_m;
		var_acc += (u64)diff_m * (u64)diff_m;
	}
	/* variance in (milli MB)^2 */
	u64 var_m2 = var_acc / n;
	/* std/mean in milli */
	u32 std_over_mean_m =
		(u32)div64_u64((u64)(1000ULL * int_sqrt64(var_m2)), mean_m ? mean_m : 1);
	return std_over_mean_m; /* typical range: 0..200 */
}


/* ------------------------
 * memcg/psi helpers (out-of-tree friendly)
 * We sample:
 *   - /proc/pressure/memory (avg10, avg60, avg300)
 *   - <cg_path>/memory.current, memory.max (bytes)  [cgroup v2]
 * cg_path is configurable via module parameter (default: /sys/fs/cgroup).
 * ------------------------ */
#include <linux/fs.h>
#include <linux/uaccess.h>

static char *cg_path = "/sys/fs/cgroup";
module_param(cg_path, charp, 0644);
MODULE_PARM_DESC(cg_path, "cgroup v2 base path (e.g., /sys/fs/cgroup, or a sub-cgroup path)");

static ssize_t read_small_file(const char *path, char *buf, size_t buflen)
{
	ssize_t ret = -ENOENT;
	struct file *filp;
	loff_t pos = 0;

	if (!path || !buf || buflen == 0)
		return -EINVAL;

	filp = filp_open(path, O_RDONLY, 0);
	if (IS_ERR(filp))
		return PTR_ERR(filp);

	ret = kernel_read(filp, buf, buflen - 1, &pos);
	if (ret >= 0)
		buf[ret] = '\0';
	filp_close(filp, NULL);
	return ret;
}

static u32 parse_psi_avg10_milli(const char *s)
{
	/* Expect line like: "some avg10=0.12 avg60=0.08 avg300=0.05 total=12345" */
	const char *p = strstr(s, "avg10=");
	if (!p) return 0;
	p += 6;
	/* parse float to milli (e.g., 0.12 -> 120) */
	long int_part = 0, frac = 0;
	int frac_digits = 0;
	/* simplistic parser */
	while (*p == ' ') p++;
	while (*p >= '0' && *p <= '9') { int_part = int_part*10 + (*p - '0'); p++; }
	if (*p == '.') {
		p++;
		while (*p >= '0' && *p <= '9' && frac_digits < 3) {
			frac = frac*10 + (*p - '0');
			frac_digits++;
			p++;
		}
		while (frac_digits++ < 3) frac *= 10;
	}
	return (u32)(int_part * 1000 + frac);
}

static u64 parse_u64_from_dec_str(const char *s)
{
	u64 v = 0;
	while (*s) {
		if (*s >= '0' && *s <= '9') {
			v = v*10 + (*s - '0');
		} else if (*s == '\n') {
			break;
		}
		s++;
	}
	return v;
}

static u32 memcg_current_mb_cached;
static u32 memcg_max_mb_cached;
static u32 psi_avg10_milli_cached;

static void sample_memcg_psi(void)
{
	char buf[256];
	ssize_t n;

	/* PSI memory avg10 from /proc/pressure/memory */
	n = read_small_file("/proc/pressure/memory", buf, sizeof(buf));
	if (n > 0)
		psi_avg10_milli_cached = parse_psi_avg10_milli(buf);

	/* cgroup v2: memory.current (bytes) */
	{
		char pcur[256];
		snprintf(pcur, sizeof(pcur), "%s/memory.current", cg_path);
		n = read_small_file(pcur, buf, sizeof(buf));
		if (n > 0) {
			u64 b = parse_u64_from_dec_str(buf);
			memcg_current_mb_cached = (u32)(b >> 20);
		}
	}

	/* cgroup v2: memory.max (bytes) may be "max" */
	{
		char pmax[256];
		snprintf(pmax, sizeof(pmax), "%s/memory.max", cg_path);
		n = read_small_file(pmax, buf, sizeof(buf));
		if (n > 0) {
			if (!strncmp(buf, "max", 3)) {
				memcg_max_mb_cached = 0; /* unlimited */
			} else {
				u64 b = parse_u64_from_dec_str(buf);
				memcg_max_mb_cached = (u32)(b >> 20);
			}
		}
	}
}

/* Sampling loop */
static void hmp_sample_fn(struct work_struct *w)
{
	sample_memcg_psi();
	unsigned long rss_mb = get_estimated_rss_mb();
	u32 limit_mb = g_params.rss_limit_mb ? g_params.rss_limit_mb : 1024;
	u32 rss_milli_of_limit = (u32)((1000ULL * rss_mb) / (limit_mb ? limit_mb : 1));

	mutex_lock(&hmp_lock);

	ring_push(rss_mb);
	u32 unstable_m = ring_volatility_milli();

	/*
	 * Utilization proxy:
	 *   Hu_m = rss/limit*1000 + alpha_milli * alloc_vel_norm
	 * We don't have real alloc/free velocity in this scaffold;
	 * approximate with volatility.
	 */
	u32 Hu_m = rss_milli_of_limit + (g_params.alpha_milli * unstable_m) / 1000;

	/* Enforcement levels via theta1/theta2 (both in milli) */
	u32 enforce_pct = 0;
	if (Hu_m > g_params.theta1_milli * 1000U) {
		enforce_pct = 30;
		if (Hu_m > g_params.theta2_milli * 1000U)
			enforce_pct = 65;
	}

	/* Tagging feedback: map instability to 90..50% multiplier */
	u32 frac = unstable_m * 35 / 100; /* rescale ~0..350 -> 0..~122 */
	if (frac > 100) frac = 100;
	u32 rate_mul_pct = 90 - (40 * frac) / 100;
	/* Apply enforcement too */
	rate_mul_pct = (rate_mul_pct * (100 - (35 * enforce_pct) / 100)) / 100;

	/* Derive proxies */
	u32 pressure_pct = clamp_u32(rss_milli_of_limit / 10, 0, 100);
	u32 lr_ms = clamp_u32(80 + (140 * pressure_pct) / 100 - (45 * enforce_pct) / 100, 40, 400);
	u32 tgc_ms = 22 - (22 * 25 / 100) * enforce_pct / 100 + (unstable_m / 20);
	u32 energy_mw = 60 + 120 * enforce_pct / 100;

	g_stats.unstable_milli = unstable_m;
	g_stats.enforce_pct = enforce_pct;
	g_stats.lr_ms = lr_ms;
	g_stats.tgc_ms = tgc_ms;
	g_stats.energy_mw = energy_mw;

	mutex_unlock(&hmp_lock);

	/* requeue */
	schedule_delayed_work(&hmp_work, msecs_to_jiffies(250));
}

/* Sysfs attributes */
static ssize_t alpha_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "%u\n", g_params.alpha_milli);
}
static ssize_t alpha_store(struct kobject *kobj, struct kobj_attribute *attr, const char *buf, size_t count)
{
	unsigned long v;
	if (kstrtoul(buf, 0, &v) == 0) {
		mutex_lock(&hmp_lock);
		g_params.alpha_milli = clamp_u32((u32)v, 0, 2000);
		mutex_unlock(&hmp_lock);
	}
	return count;
}
static struct kobj_attribute alpha_attr = __ATTR(alpha, 0644, alpha_show, alpha_store);

static ssize_t theta1_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "%u\n", g_params.theta1_milli);
}
static ssize_t theta1_store(struct kobject *kobj, struct kobj_attribute *attr, const char *buf, size_t count)
{
	unsigned long v;
	if (kstrtoul(buf, 0, &v) == 0) {
		mutex_lock(&hmp_lock);
		g_params.theta1_milli = clamp_u32((u32)v, 0, 5000);
		mutex_unlock(&hmp_lock);
	}
	return count;
}
static struct kobj_attribute theta1_attr = __ATTR(theta1, 0644, theta1_show, theta1_store);

static ssize_t theta2_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "%u\n", g_params.theta2_milli);
}
static ssize_t theta2_store(struct kobject *kobj, struct kobj_attribute *attr, const char *buf, size_t count)
{
	unsigned long v;
	if (kstrtoul(buf, 0, &v) == 0) {
		mutex_lock(&hmp_lock);
		g_params.theta2_milli = clamp_u32((u32)v, 0, 5000);
		mutex_unlock(&hmp_lock);
	}
	return count;
}
static struct kobj_attribute theta2_attr = __ATTR(theta2, 0644, theta2_show, theta2_store);

static ssize_t rss_limit_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "%u\n", g_params.rss_limit_mb);
}
static ssize_t rss_limit_store(struct kobject *kobj, struct kobj_attribute *attr, const char *buf, size_t count)
{
	unsigned long v;
	if (kstrtoul(buf, 0, &v) == 0) {
		mutex_lock(&hmp_lock);
		g_params.rss_limit_mb = clamp_u32((u32)v, 128, 65536);
		mutex_unlock(&hmp_lock);
	}
	return count;
}
static struct kobj_attribute rss_limit_attr = __ATTR(rss_limit, 0644, rss_limit_show, rss_limit_store);

static ssize_t stats_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf)
{
	struct hmp_stats s;
	mutex_lock(&hmp_lock);
	s = g_stats;
	mutex_unlock(&hmp_lock);
	return scnprintf(buf, PAGE_SIZE,
		"unstable_milli=%u\npsi_avg10_milli=%u\nmemcg_current_mb=%u\nmemcg_max_mb=%u\nenforce_pct=%u\nlr_ms=%u\ntgc_ms=%u\nenergy_mw=%u\n",
		s.unstable_milli, psi_avg10_milli_cached, memcg_current_mb_cached, memcg_max_mb_cached, s.enforce_pct, s.lr_ms, s.tgc_ms, s.energy_mw);
}
static struct kobj_attribute stats_attr = __ATTR(stats, 0444, stats_show, NULL);

static struct attribute *hmp_attrs[] = {
	&alpha_attr.attr,
	&theta1_attr.attr,
	&theta2_attr.attr,
	&rss_limit_attr.attr,
	&stats_attr.attr,
	NULL,
};

static const struct attribute_group hmp_attr_group = {
	.attrs = hmp_attrs,
};

static int __init hmp_init(void)
{
	int ret;

	hmp_kobj = kobject_create_and_add("hmp", kernel_kobj);
	if (!hmp_kobj)
		return -ENOMEM;

	ret = sysfs_create_group(hmp_kobj, &hmp_attr_group);
	if (ret) {
		kobject_put(hmp_kobj);
		return ret;
	}

	INIT_DELAYED_WORK(&hmp_work, hmp_sample_fn);
	schedule_delayed_work(&hmp_work, msecs_to_jiffies(250));

	if (misc_register(&hmp_misc)) {
		pr_err(DRV_NAME ": failed to register /dev/%s\n", HMP_CTL_NAME);
		return -ENODEV;
	}
	pr_info(DRV_NAME ": /dev/%s ready\n", HMP_CTL_NAME);
	pr_info(DRV_NAME ": initialized (alpha=%u, theta1=%u, theta2=%u, rss_limit=%uMB)\n",
		g_params.alpha_milli, g_params.theta1_milli, g_params.theta2_milli, g_params.rss_limit_mb);
	return 0;
}

static void __exit hmp_exit(void)
{
	cancel_delayed_work_sync(&hmp_work);
	if (hmp_kobj) {
		sysfs_remove_group(hmp_kobj, &hmp_attr_group);
		kobject_put(hmp_kobj);
	}
	misc_deregister(&hmp_misc);
	pr_info(DRV_NAME ": unloaded\n");
}

module_init(hmp_init);
module_exit(hmp_exit);

MODULE_AUTHOR("HMP Research Artifact");
MODULE_DESCRIPTION("Heap Memory Protector kernel module (research scaffold)");
MODULE_LICENSE("Apache-2.0");

import numpy as np

class Telemetry:
    """Generates synthetic allocation/free streams and derived metrics.

    Each workload returns a dict with time series for:
      - alloc_rate: allocations per unit time (MB/s)
      - free_rate: frees per unit time (MB/s)
      - rss: resident set size (MB)
      - cpu_util: CPU utilization (0..1)
    """

    def __init__(self, seed: int = 7, steps: int = 1800, dt: float = 0.1):
        self.rng = np.random.default_rng(seed)
        self.steps = steps
        self.dt = dt

    def _mk(self, alloc_base, burst_prob, burst_scale, drift, noise):
        N = self.steps
        rss = np.zeros(N)
        alloc_rate = np.zeros(N)
        free_rate = np.zeros(N)
        cpu_util = np.zeros(N)
        rss_val = 120.0  # MB
        for t in range(N):
            # bursts
            a = alloc_base * (1.0 + self.rng.normal(0, noise))
            if self.rng.random() < burst_prob:
                a += burst_scale * self.rng.random()
            f = max(0.0, a * (0.85 + 0.25 * self.rng.random()))
            # drift
            rss_val = max(40.0, rss_val + (a - f) * self.dt + drift)
            alloc_rate[t] = max(0.0, a)
            free_rate[t] = max(0.0, f)
            rss[t] = rss_val + self.rng.normal(0, 1.5)
            cpu_util[t] = np.clip(0.25 + 0.35 * (a / (alloc_base + 1e-6)) + self.rng.normal(0,0.05), 0, 1)
        return {
            "alloc_rate": alloc_rate,
            "free_rate": free_rate,
            "rss": rss,
            "cpu_util": cpu_util,
            "dt": self.dt,
        }

    def workload_w1(self):
        """W1: foreground app with periodic camera bursts."""
        return self._mk(alloc_base=32, burst_prob=0.08, burst_scale=90, drift=0.01, noise=0.18)

    def workload_w2(self):
        """W2: ML inference background service with spiky load."""
        return self._mk(alloc_base=22, burst_prob=0.15, burst_scale=60, drift=0.005, noise=0.22)

    def workload_w3(self):
        """W3: mixed UI + I/O with occasional leaks."""
        return self._mk(alloc_base=18, burst_prob=0.05, burst_scale=55, drift=0.02, noise=0.15)

    def workload_w4(self):
        """W4: steady playback with rare GC stalls."""
        return self._mk(alloc_base=12, burst_prob=0.02, burst_scale=40, drift=0.0, noise=0.1)

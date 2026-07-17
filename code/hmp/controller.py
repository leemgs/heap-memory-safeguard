import numpy as np
from collections import deque
from .memcg import MemcgReclaimer
from .tagging import TaggingUnit

class HMPController:
    def __init__(self, alpha=0.35, theta1=0.12, theta2=0.18, rss_limit_mb=1024.0):
        self.alpha = alpha
        self.theta1 = theta1
        self.theta2 = theta2
        self.memcg = MemcgReclaimer(rss_limit_mb=rss_limit_mb)
        self.tag = TaggingUnit()
        self.growth_window = deque(maxlen=120)
        self.smoothed_growth = 0.0

    def step(self, state, rss_hist):
        # state: dict with alloc_rate, free_rate, rss (current), cpu_util
        rss = state['rss']
        alloc = state['alloc_rate']
        free = state['free_rate']

        # Online-only normalization: no whole-trace maximum or future samples.
        net_growth = alloc - free
        self.smoothed_growth = 0.8 * self.smoothed_growth + 0.2 * net_growth
        self.growth_window.append(abs(self.smoothed_growth))
        growth_scale = max(1e-6, float(np.percentile(self.growth_window, 95)))
        normalized_growth = np.clip(self.smoothed_growth / growth_scale, 0.0, 1.0)
        Hu = (rss / self.memcg.limit) + self.alpha * normalized_growth

        frac_unstable = self.tag.unstable_fraction(rss_hist)
        rate_mul = 1.0
        enforce_level = 0.0

        if Hu > self.theta1:
            enforce_level = 0.3
            if Hu > self.theta2:
                enforce_level = 0.65

        # tagging feedback
        rate_mul *= self.tag.rate_limit(frac_unstable)
        rate_mul *= (1.0 - 0.35 * enforce_level)

        # estimate pressure (0..1) for reclaim latency
        pressure = float(np.clip(rss / self.memcg.limit, 0, 1))
        Lr = self.memcg.reclaim_latency_ms(pressure, aggressiveness=enforce_level)

        # GC pause proxy (reduced under better control)
        Tgc = 22.0 * (1.0 - 0.25 * enforce_level) * (1.0 + 0.5 * frac_unstable)

        # energy overhead: small tax when enforcing
        Eo = 0.06 + 0.12 * enforce_level

        return {
            "Hu": Hu,
            "rate_mul": rate_mul,
            "Lr_ms": Lr,
            "Tgc_ms": Tgc,
            "Eo_W": Eo,
            "unstable": frac_unstable,
            "enforce": enforce_level,
        }

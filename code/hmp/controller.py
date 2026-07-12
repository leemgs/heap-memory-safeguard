import numpy as np
from .memcg import MemcgReclaimer
from .tagging import TaggingUnit

class HMPController:
    def __init__(self, alpha=0.35, theta1=0.12, theta2=0.18, rss_limit_mb=1024.0):
        self.alpha = alpha
        self.theta1 = theta1
        self.theta2 = theta2
        self.memcg = MemcgReclaimer(rss_limit_mb=rss_limit_mb)
        self.tag = TaggingUnit()

    def step(self, state, rss_hist):
        # state: dict with alloc_rate, free_rate, rss (current), cpu_util
        rss = state['rss']
        alloc = state['alloc_rate']
        free = state['free_rate']

        # utilization index Hu ~= rss/limit + alpha * (alloc_velocity/max)
        # approximate alloc velocity by alloc - free (clipped)
        alloc_vel = max(0.0, alloc - free)
        Hu = (rss / self.memcg.limit) + self.alpha * (alloc_vel / (alloc + 1e-6))

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

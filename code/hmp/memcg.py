import numpy as np

class MemcgReclaimer:
    def __init__(self, rss_limit_mb: float = 1024.0):
        self.limit = rss_limit_mb

    def reclaim_latency_ms(self, pressure: float, aggressiveness: float):
        """Toy function: higher pressure and aggressiveness vary latency."""
        base = 80.0 + 140.0 * pressure
        # more aggressive generally lowers latency until a point
        return max(40.0, base * (1.0 - 0.45 * np.clip(aggressiveness, 0, 1)))

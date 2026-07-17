import numpy as np

class TaggingUnit:
    """A volatility proxy; this is unrelated to Arm MTE fault detection."""
    def __init__(self, granule_mb: float = 0.0625):
        self.granule = granule_mb

    def unstable_fraction(self, rss_series: np.ndarray, window: int = 30):
        if len(rss_series) < window:
            return 0.0
        # normalized volatility as an 'instability' proxy
        w = rss_series[-window:]
        denom = np.mean(w) + 1e-6
        return float(np.std(w) / denom)

    def rate_limit(self, frac_unstable: float):
        # convert instability (0..~0.2+) into a [0.9..0.5] multiplier
        frac = np.clip(frac_unstable * 3.5, 0, 1)
        return 0.9 - 0.4 * frac

import numpy as np
import pandas as pd
from .telemetry import Telemetry
from .controller import HMPController

def _heap_stability(rss):
    # 1 - normalized stddev of rss
    m = np.mean(rss) + 1e-6
    return float(np.clip(1.0 - (np.std(rss) / m), 0.0, 1.0))

def _simulate_series(workload_fn, controller: HMPController | None):
    tel = Telemetry()
    trace = workload_fn()
    dt = trace['dt']
    rss_hist = []
    Lr_list, Tgc_list, Eo_list = [], [], []
    rss_series = []

    for i in range(len(trace['rss'])):
        state = {k: float(trace[k][i]) if k in ('alloc_rate','free_rate','rss','cpu_util') else trace[k]
                 for k in trace}
        rss_hist.append(state['rss'])
        if controller is None:
            # baseline: no control, slight random reclaim
            Lr = 80 + 140 * min(1.0, state['rss']/1024.0) + 10 * np.random.rand()
            Tgc = 21.0 + 6.0 * np.random.rand()
            Eo = 0.0
            rss_series.append(state['rss'] + np.random.normal(0, 2.0))
        else:
            info = controller.step(state, np.array(rss_hist[-45:]))
            Lr, Tgc, Eo = info['Lr_ms'], info['Tgc_ms'], info['Eo_W']
            # apply rate multiplier to allocation -> lower rss growth
            delta = (state['alloc_rate'] - state['free_rate']) * dt
            delta *= info['rate_mul']
            new_rss = max(40.0, (rss_series[-1] if rss_series else state['rss']) + delta + np.random.normal(0,1.0))
            rss_series.append(new_rss)

        Lr_list.append(Lr); Tgc_list.append(Tgc); Eo_list.append(Eo)

    return {
        "rss": np.array(rss_series),
        "Lr_ms": np.array(Lr_list),
        "Tgc_ms": np.array(Tgc_list),
        "Eo_W": np.array(Eo_list),
    }

def run_all(alpha=0.35, theta1=0.12, theta2=0.18, rss_limit_mb=1024.0, seed=7):
    workloads = {
        "W1": Telemetry(seed=seed).workload_w1,
        "W2": Telemetry(seed=seed+1).workload_w2,
        "W3": Telemetry(seed=seed+2).workload_w3,
        "W4": Telemetry(seed=seed+3).workload_w4,
    }
    ctrl = HMPController(alpha=alpha, theta1=theta1, theta2=theta2, rss_limit_mb=rss_limit_mb)

    rows = []
    for name, fn in workloads.items():
        base = _simulate_series(fn, controller=None)
        hmp = _simulate_series(fn, controller=ctrl)

        Sh_base = _heap_stability(base['rss'])
        Sh_hmp = _heap_stability(hmp['rss'])
        Lr_base = float(np.percentile(base['Lr_ms'], 50))
        Lr_hmp = float(np.percentile(hmp['Lr_ms'], 50))
        Tgc_base = float(np.percentile(base['Tgc_ms'], 50))
        Tgc_hmp = float(np.percentile(hmp['Tgc_ms'], 50))
        peak_rss_red = 100.0 * (np.max(base['rss']) - np.max(hmp['rss'])) / (np.max(base['rss']) + 1e-6)
        Eo = float(np.mean(hmp['Eo_W']))

        rows.append({
            "workload": name,
            "Sh_base": Sh_base, "Sh_hmp": Sh_hmp, "Sh_impr_pct": 100*(Sh_hmp - Sh_base)/(Sh_base+1e-6),
            "Lr_base_ms": Lr_base, "Lr_hmp_ms": Lr_hmp, "Lr_impr_pct": 100*(Lr_base - Lr_hmp)/max(1e-6,Lr_base),
            "Tgc_base_ms": Tgc_base, "Tgc_hmp_ms": Tgc_hmp, "Tgc_impr_pct": 100*(Tgc_base - Tgc_hmp)/max(1e-6,Tgc_base),
            "Peak_RSS_Reduction_pct": peak_rss_red,
            "Energy_Overhead_W": Eo,
        })
    return pd.DataFrame(rows)

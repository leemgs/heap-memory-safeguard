#!/usr/bin/env python3
import argparse, os, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from hmp.evaluation import run_all

def ensure_dir(d):
    os.makedirs(d, exist_ok=True)

def main():
    ap = argparse.ArgumentParser(description="Reproduce HMP results (simulation)")
    ap.add_argument("--alpha", type=float, default=0.35)
    ap.add_argument("--theta1", type=float, default=0.12)
    ap.add_argument("--theta2", type=float, default=0.18)
    ap.add_argument("--rss-limit", type=float, default=1024.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--outdir", type=str, default="results")
    args = ap.parse_args()

    ensure_dir(args.outdir)
    ensure_dir(os.path.join(args.outdir, "figures"))
    ensure_dir(os.path.join(args.outdir, "metrics"))

    df = run_all(alpha=args.alpha, theta1=args.theta1, theta2=args.theta2,
                 rss_limit_mb=args.rss_limit, seed=args.seed)

    # Save metrics
    metrics_path = os.path.join(args.outdir, "metrics", "summary.csv")
    df.to_csv(metrics_path, index=False)

    # Print a compact table
    print(df.to_string(index=False))

    # Generate parameter sensitivity figure (alpha, theta1, theta2)
    # We'll sweep alpha and keep others fixed, then sweep theta1/theta2 on grids.
    alphas = [0.2, 0.35, 0.55, 0.7]
    alpha_scores = []
    for a in alphas:
        d = run_all(alpha=a, theta1=args.theta1, theta2=args.theta2, rss_limit_mb=args.rss_limit, seed=args.seed)
        alpha_scores.append(d["Sh_hmp"].mean())

    # Plot: alpha vs stability (fig9_W1_alpha_vs_Sh_3alpha.png style proxy)
    plt.figure()
    plt.plot(alphas, alpha_scores, marker="o")
    plt.xlabel("alpha")
    plt.ylabel("Heap stability (mean across W1-W4)")
    plt.title("Parameter sensitivity: alpha vs S_h")
    fig1 = os.path.join(args.outdir, "figures", "fig9_W1_alpha_vs_Sh_3alpha.png")
    plt.savefig(fig1, dpi=160, bbox_inches="tight")
    plt.close()

    # theta1 vs Lr (median across workloads)
    theta1s = np.linspace(0.08, 0.2, 6)
    t1_scores = []
    for t1 in theta1s:
        d = run_all(alpha=args.alpha, theta1=t1, theta2=args.theta2, rss_limit_mb=args.rss_limit, seed=args.seed)
        t1_scores.append(d["Lr_hmp_ms"].median())
    plt.figure()
    plt.plot(theta1s, t1_scores, marker="o")
    plt.xlabel("theta1")
    plt.ylabel("Reclaim latency (ms, median)")
    plt.title("Parameter sensitivity: theta1 vs L_r")
    fig2 = os.path.join(args.outdir, "figures", "fig9_W2_theta1_vs_Lr.png")
    plt.savefig(fig2, dpi=160, bbox_inches="tight")
    plt.close()

    # theta2 vs Sh and vs Lr
    theta2s = np.linspace(0.12, 0.28, 6)
    t2_sh, t2_lr = [], []
    for t2 in theta2s:
        d = run_all(alpha=args.alpha, theta1=args.theta1, theta2=t2, rss_limit_mb=args.rss_limit, seed=args.seed)
        t2_sh.append(d["Sh_hmp"].mean())
        t2_lr.append(d["Lr_hmp_ms"].median())

    plt.figure()
    plt.plot(theta2s, t2_sh, marker="o")
    plt.xlabel("theta2")
    plt.ylabel("Heap stability (mean)")
    plt.title("Parameter sensitivity: theta2 vs S_h")
    fig3 = os.path.join(args.outdir, "figures", "fig9_W3_theta2_vs_Sh.png")
    plt.savefig(fig3, dpi=160, bbox_inches="tight")
    plt.close()

    plt.figure()
    plt.plot(theta2s, t2_lr, marker="o")
    plt.xlabel("theta2")
    plt.ylabel("Reclaim latency (ms, median)")
    plt.title("Parameter sensitivity: theta2 vs L_r")
    fig4 = os.path.join(args.outdir, "figures", "fig9_W4_theta2_vs_Lr.png")
    plt.savefig(fig4, dpi=160, bbox_inches="tight")
    plt.close()

    # Combined simple sensitivity figure
    plt.figure()
    plt.plot(alphas, alpha_scores, marker="o")
    plt.xlabel("alpha")
    plt.ylabel("S_h (mean)")
    plt.title("Parameter sensitivity summary")
    fig5 = os.path.join(args.outdir, "figures", "fig_param_sensitivity.png")
    plt.savefig(fig5, dpi=160, bbox_inches="tight")
    plt.close()

    print(f"Saved metrics to {metrics_path}")
    print(f"Saved figures to {os.path.join(args.outdir, 'figures')}")

if __name__ == "__main__":
    main()

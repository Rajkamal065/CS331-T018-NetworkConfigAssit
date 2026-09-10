"""
tools/plots.py — Before/After benchmark bar charts using matplotlib.

Generates side-by-side comparison PNG files saved to /app/results/.
Each chart has:
  Left panel:  Grouped bar chart — Before vs After values (ms)
  Right panel: Horizontal bar chart — Percentage improvement
"""

import os
from typing import Dict, Any

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def _ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def generate_comparison_chart(comparison: Dict[str, Any],
                               profile_name: str) -> str:
    """
    Generate a before/after comparison bar chart.
    Returns the absolute file path of the saved PNG, or an error string.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")   # Non-interactive backend — no display needed
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return "ERROR: matplotlib not installed. Run: pip install matplotlib numpy"

    _ensure_results_dir()

    # ── Collect metrics that have valid before AND after values ───────
    metrics      = []
    before_vals  = []
    after_vals   = []
    pct_changes  = []

    metric_map = {
        "latency_avg":      "Avg Latency (ms)",
        "jitter":           "Jitter (ms)",
        "latency_max":      "Max Latency (ms)",
        "tcp_connect_avg":  "TCP Connect (ms)",
    }

    for key, label in metric_map.items():
        entry = comparison.get(key, {})
        b = entry.get("before_ms")
        a = entry.get("after_ms")
        p = entry.get("improvement_pct")
        if b is not None and a is not None:
            metrics.append(label)
            before_vals.append(b)
            after_vals.append(a)
            pct_changes.append(p if p is not None else 0.0)

    if not metrics:
        return "ERROR: No benchmark metrics available to plot"

    # ── Figure Layout ─────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(
        f"NetOps Assistant — {profile_name.title()} Profile: Before vs After",
        fontsize=14, fontweight="bold", y=1.01
    )

    x      = np.arange(len(metrics))
    width  = 0.35
    BEFORE_COLOR = "#ff6b6b"   # Red-ish
    AFTER_COLOR  = "#51cf66"   # Green-ish
    PCT_POS      = "#339af0"   # Blue (improvement)
    PCT_NEG      = "#ff6b6b"   # Red (regression)

    # ── Left: Grouped Bar Chart (raw ms values) ───────────────────────
    bars1 = ax1.bar(x - width / 2, before_vals, width,
                    label="Before (Default)", color=BEFORE_COLOR, alpha=0.85,
                    edgecolor="black", linewidth=0.8)
    bars2 = ax1.bar(x + width / 2, after_vals, width,
                    label=f"After ({profile_name.title()})", color=AFTER_COLOR, alpha=0.85,
                    edgecolor="black", linewidth=0.8)

    ax1.set_ylabel("Time (ms)", fontsize=11, fontweight="bold")
    ax1.set_title("Raw Measurements: Before vs After", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(metrics, fontsize=9)
    ax1.legend(fontsize=10)
    ax1.grid(axis="y", alpha=0.3, linestyle="--")
    ax1.set_axisbelow(True)

    # Value labels on bars
    for bar in list(bars1) + list(bars2):
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2., h + 0.3,
                 f"{h:.1f}", ha="center", va="bottom", fontsize=8)

    # ── Right: Horizontal % Improvement Chart ─────────────────────────
    colors = [PCT_POS if p >= 0 else PCT_NEG for p in pct_changes]
    bars3 = ax2.barh(metrics, pct_changes, color=colors, alpha=0.85,
                     edgecolor="black", linewidth=0.8)

    ax2.set_xlabel("Improvement (%)", fontsize=11, fontweight="bold")
    ax2.set_title("Performance Improvement (%)", fontsize=12, fontweight="bold")
    ax2.axvline(x=0, color="black", linewidth=1.2)
    ax2.grid(axis="x", alpha=0.3)
    ax2.set_axisbelow(True)

    # Percentage labels
    for bar, pct in zip(bars3, pct_changes):
        w = bar.get_width()
        label_x = w + (1 if w >= 0 else -1)
        ha = "left" if w >= 0 else "right"
        ax2.text(label_x, bar.get_y() + bar.get_height() / 2.,
                 f"{pct:+.1f}%", ha=ha, va="center",
                 fontsize=9, fontweight="bold")

    plt.tight_layout()

    filename = f"{profile_name.lower()}_benchmark.png"
    filepath = os.path.join(RESULTS_DIR, filename)
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return filepath

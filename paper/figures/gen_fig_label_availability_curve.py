"""Generate the publication figure for MGA-Hybrid label availability."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(args.summary.read_text(encoding="utf-8"))
    curve = data["curve"]
    x = np.asarray([point["availability"] * 100 for point in curve])

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.titleweight": "bold",
            "axes.labelsize": 9,
            "legend.fontsize": 7.5,
            "legend.frameon": False,
            "figure.dpi": 300,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.16,
            "grid.linestyle": "-",
            "lines.linewidth": 1.8,
            "lines.markersize": 4.5,
        }
    )
    colors = {
        "neutral_auc": "#0072B2",
        "balanced_accuracy": "#009E73",
        "false_support_rate": "#D55E00",
        "coverage": "#56B4E9",
        "unverifiable_rate": "#CC79A7",
    }
    labels = {
        "neutral_auc": "Neutral AUC ↑",
        "balanced_accuracy": "Balanced Accuracy ↑",
        "false_support_rate": "False Support Rate ↓",
        "coverage": "Coverage ↑",
        "unverifiable_rate": "Unverifiable Rate ↓",
    }
    markers = {
        "neutral_auc": "o",
        "balanced_accuracy": "s",
        "false_support_rate": "^",
        "coverage": "D",
        "unverifiable_rate": "v",
    }

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(6.75, 2.65),
        gridspec_kw={"width_ratios": [1.7, 1.0], "wspace": 0.28},
    )
    ax = axes[0]
    for metric in ("neutral_auc", "balanced_accuracy", "false_support_rate"):
        y = np.asarray([point[metric] for point in curve])
        low = np.asarray([point[f"{metric}_min"] for point in curve])
        high = np.asarray([point[f"{metric}_max"] for point in curve])
        ax.plot(
            x,
            y,
            label=labels[metric],
            color=colors[metric],
            marker=markers[metric],
            zorder=3,
        )
        ax.fill_between(x, low, high, color=colors[metric], alpha=0.10, linewidth=0)
    ax.set_title("(a) Evidence discrimination")
    ax.set_xlabel("Available semantic classes (%)")
    ax.set_ylabel("Metric value")
    ax.set_xlim(-2, 102)
    ax.set_ylim(0.0, 1.0)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{value:.0f}" for value in x])
    ax.legend(loc="upper left")
    ax.annotate(
        "MGA-OV endpoint",
        xy=(x[0], curve[0]["neutral_auc"]),
        xytext=(12, 0.48),
        textcoords="data",
        fontsize=7,
        color="#4A4A4A",
        arrowprops={"arrowstyle": "-", "color": "#888888", "lw": 0.8},
    )
    ax.annotate(
        "Full semantic evidence",
        xy=(x[-1], curve[-1]["neutral_auc"]),
        xytext=(61, 0.84),
        textcoords="data",
        fontsize=7,
        color="#4A4A4A",
        arrowprops={"arrowstyle": "-", "color": "#888888", "lw": 0.8},
    )

    ax = axes[1]
    for metric in ("coverage", "unverifiable_rate"):
        y = np.asarray([point[metric] for point in curve])
        ax.plot(
            x,
            y,
            label=labels[metric],
            color=colors[metric],
            marker=markers[metric],
            zorder=3,
        )
    ax.set_title("(b) Evaluation availability")
    ax.set_xlabel("Available semantic classes (%)")
    ax.set_ylabel("Rate")
    ax.set_xlim(-2, 102)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{value:.0f}" for value in x])
    ax.legend(loc="center right")
    ax.text(
        50,
        0.50,
        "OV fallback preserves\nfull score coverage",
        ha="center",
        va="center",
        fontsize=7.5,
        color="#4A4A4A",
    )

    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output_prefix.with_suffix(".pdf"))
    fig.savefig(args.output_prefix.with_suffix(".png"), dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    main()

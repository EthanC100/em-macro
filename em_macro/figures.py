"""README figures (static PNG)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import FIT_END, PROC, RESULTS

FIT_C, TEST_C = "#2a78d6", "#eb6834"          # categorical slots 1 and 2
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def carry_chart():
    r = pd.read_csv(PROC / "carry_monthly_returns.csv", index_col=0)
    r.index = pd.PeriodIndex(r.index, freq="M").to_timestamp(how="end")
    w = (1 + r["EW"]).cumprod()
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    ax.axvspan(pd.Timestamp("2022-01-01"), w.index[-1], color=GRID, alpha=0.6, lw=0)
    ax.text(pd.Timestamp("2022-03-01"), w.max() * 1.02, "hold-out", color=MUTED, fontsize=9, va="top")
    ax.plot(w.index, w.values, color=FIT_C, lw=2)
    ax.axhline(1, color=MUTED, lw=0.8)
    ax.set_title("Carry benchmark, equal-weight basket of 6 EM currencies (growth of 1 USD, after costs)",
                 loc="left", fontsize=10, color=INK)
    _style(ax)
    fig.tight_layout()
    fig.savefig(RESULTS / "fig_carry_basket.png")
    plt.close(fig)


def election_surprise_chart():
    fit = pd.read_csv(RESULTS / "fit" / "event_moves.csv")
    test = pd.read_csv(RESULTS / "test" / "event_moves.csv")
    sel = lambda m: m[(m.event_type == "election") & (m.asset == "FX")].dropna(subset=["surprise_mp_pp", "ab_1"])
    fit, test = sel(fit), sel(test)
    b = np.polyfit(fit.surprise_mp_pp, fit.ab_1, 1)
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    xs = np.linspace(min(fit.surprise_mp_pp.min(), test.surprise_mp_pp.min()) - 1,
                     max(fit.surprise_mp_pp.max(), test.surprise_mp_pp.max()) + 1, 50)
    ax.plot(xs, np.polyval(b, xs), color=FIT_C, lw=1.5, ls="--")
    ax.scatter(fit.surprise_mp_pp, fit.ab_1, s=40, color=FIT_C, edgecolor="white", lw=1.5,
               label=f"2005-2021 (fit), n={len(fit)}", zorder=3)
    ax.scatter(test.surprise_mp_pp, test.ab_1, s=48, color=TEST_C, edgecolor="white", lw=1.5, marker="D",
               label=f"2022+ (hold-out), n={len(test)}", zorder=3)
    for r in test.itertuples():
        ax.annotate(f"{r.country} {r.event_id[-8:-4]}", (r.surprise_mp_pp, r.ab_1), fontsize=7, color=MUTED,
                    xytext=(4, 3), textcoords="offset points")
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("poll surprise, pp (+ = market-preferred side beat its final poll margin)", fontsize=9, color=MUTED)
    ax.set_ylabel("abnormal FX move, day 1, %\n(+ = local currency up)", fontsize=9, color=MUTED)
    ax.set_title("Election-day currency moves vs. poll surprise (dashed: fit-sample OLS)", loc="left",
                 fontsize=10, color=INK)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _style(ax)
    fig.tight_layout()
    fig.savefig(RESULTS / "fig_election_surprise.png")
    plt.close(fig)


if __name__ == "__main__":
    carry_chart()
    election_surprise_chart()

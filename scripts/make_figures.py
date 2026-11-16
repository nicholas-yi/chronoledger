"""Regenerate the README figures from checked-in result files.

Run from the repository root:  python scripts/make_figures.py
Requires the optional ``figures`` extra (matplotlib). No data downloads, backtests
or model calls: every number is read from ``results/``. Each figure is written in a
light and a dark variant so it stays readable in both GitHub themes.

Design choices follow Rougier, Droettboom & Bourne (2014), "Ten Simple Rules for
Better Figures", and Wilke, "Fundamentals of Data Visualization": a takeaway title,
direct labels instead of legends, and the colour-blind-safe Okabe-Ito palette.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = ROOT / "docs" / "figures"

# Okabe-Ito palette.
BLUE, ORANGE, GREEN, VERMILLION = "#0072B2", "#E69F00", "#009E73", "#D55E00"
SKY, PURPLE = "#56B4E9", "#CC79A7"

THEMES = {
    "light": {"bg": "#ffffff", "ink": "#1f2328", "muted": "#59636e", "grid": "#d8dee4"},
    "dark": {"bg": "#0d1117", "ink": "#e6edf3", "muted": "#9198a1", "grid": "#30363d"},
}
T = THEMES["light"]


def _use_theme(name: str) -> None:
    global T, BLUE
    T = THEMES[name]
    BLUE = SKY if name == "dark" else "#0072B2"
    plt.rcParams.update({
        "svg.fonttype": "none",
        "svg.hashsalt": "filing-time-machine",
        "font.family": "sans-serif",
        "font.size": 11,
        "figure.facecolor": T["bg"],
        "axes.facecolor": T["bg"],
        "savefig.facecolor": T["bg"],
        "axes.edgecolor": T["muted"],
        "axes.labelcolor": T["ink"],
        "axes.titlecolor": T["ink"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": T["grid"],
        "grid.linewidth": 0.6,
        "xtick.color": T["ink"],
        "ytick.color": T["ink"],
        "text.color": T["ink"],
        "legend.labelcolor": T["ink"],
    })


def _load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def _title(fig, text: str) -> None:
    fig.suptitle(text, x=0.01, ha="left", fontsize=12.5, fontweight="bold")


def time_machine(theme: str):
    """Illustration, not data: valid time versus knowledge time for one 10-K."""
    d = datetime.fromisoformat
    fig, ax = plt.subplots(figsize=(10, 3.9), layout="constrained")
    ax.grid(False)
    ax.barh(2, d("2023-01-01") - d("2022-07-01"), left=d("2022-07-01"), height=0.45,
            color=BLUE)
    ax.text(d("2022-09-30"), 2, "fiscal year 2022 →", ha="center", va="center",
            color="white", fontsize=10, fontweight="bold")
    for when, label, color in (("2023-02-22", "10-K accepted\nrevenue = $100M", GREEN),
                               ("2023-06-01", "10-K/A accepted\nrevenue restated to $92M",
                                VERMILLION)):
        ax.scatter(d(when), 1, s=110, color=color, zorder=3)
        ax.text(d(when), 0.7, label, ha="center", va="top", fontsize=9.5)
    for when, label in (("2023-01-10", "ask as of Jan 10\n→ nothing yet"),
                        ("2023-04-15", "ask as of Apr 15\n→ $100M"),
                        ("2023-08-01", "ask as of Aug 1\n→ $92M")):
        ax.axvline(d(when), color=T["muted"], ls="--", lw=1)
        ax.text(d(when), 2.5, label, ha="center", va="bottom", fontsize=9.5)
    ax.set_yticks([1, 2], ["when the market\ncould know it", "what period\nit describes"])
    ax.set_ylim(-0.1, 3.3)
    ax.set_xlim(d("2022-07-01"), d("2023-09-15"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    _title(fig, "Every fact carries two clocks, and a query only sees what was public then")
    return fig


def development_returns(theme: str):
    """Cumulative net long-short returns on the 2023-2024 development sample."""
    fig, ax = plt.subplots(figsize=(10, 4.2), layout="constrained")
    for color, result in zip((BLUE, ORANGE, GREEN, PURPLE),
                             _load("returns_h0_development.json")["results"]):
        series = result["monthly_return_series"]["0.0"]
        first = datetime.strptime(series[0]["return_month"], "%Y-%m")
        start = (first.replace(year=first.year - 1, month=12) if first.month == 1
                 else first.replace(month=first.month - 1))
        months = [start] + [datetime.strptime(p["return_month"], "%Y-%m") for p in series]
        wealth, path = 1.0, [0.0]
        for p in series:
            wealth *= 1 + p["ls_net"]
            path.append(100 * (wealth - 1))
        ax.plot(months, path, color=color, lw=2.2)
        ax.text(months[-1], path[-1], "  " + result["variant"].replace("_", " "),
                color=color, va="center", fontsize=9.5, fontweight="bold")
    ax.axhline(0, color=T["muted"], lw=0.8)
    ax.set_ylabel("cumulative net return, %")
    ax.set_xticks([datetime(y, m, 1) for y, m in
                   ((2023, 1), (2023, 4), (2023, 7), (2023, 10), (2024, 1), (2024, 4), (2024, 7))])
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.set_xlim(right=datetime(2024, 11, 15))
    _title(fig, "Lazy Prices, 2023-2024: no variant earns a reliable premium after costs")
    return fig


def leak_probe(theme: str):
    """ChronoBERT neologism probe: rank of a masked term in evoking vs control sentences."""
    rows = _load("leakprobe_chronobert.json")
    terms = ["COVID", "coronavirus", "Brexit"]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 4.1), sharey=True, layout="constrained")
    for ax, term in zip(axes, terms):
        sub = [r for r in rows if r["term"] == term]
        vintages = sorted({r["vintage"] for r in sub})
        xs = range(len(vintages))
        for i, v in enumerate(vintages):
            if next(r["before_first_use"] for r in sub if r["vintage"] == v):
                ax.axvspan(i - 0.42, i + 0.42, color=ORANGE, alpha=0.15, lw=0)
        for context, color, marker in (("evoking", VERMILLION, "o"), ("control", T["muted"], "s")):
            ranks = [next(r["first_rank"] for r in sub
                          if r["vintage"] == v and r["context"] == context) for v in vintages]
            ax.plot(list(xs), ranks, marker=marker, color=color, lw=1.8, ms=6)
            if term == "COVID":
                ax.text(1, ranks[1] * 3.2, f"{context} sentence", color=color, ha="center",
                        fontsize=9)
        ax.set_xticks(list(xs), [v[:4] for v in vintages])
        ax.set_yscale("log")
        ax.set_title(term, fontsize=11, fontweight="bold")
        ax.set_xlabel("model vintage (year-end)")
    axes[0].invert_yaxis()
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    axes[0].set_ylabel("rank of the hidden word\n(1 = model's top guess)")
    axes[0].text(0, 25, "trained before\nthe word existed", color=ORANGE, fontsize=8.5,
                 ha="center")
    _title(fig, "A language model dated 2018 already completes '___-19' with 'COVID'")
    return fig


def test_size(theme: str):
    """Synthetic null: how often each test 'finds' an effect that is not there."""
    cal = _load("robust_inference_calibration.json")
    monthly = (("registered_NW6", "textbook Newey-West", VERMILLION),
               ("NW_fixed_b", "Newey-West + fixed-b", ORANGE),
               ("EWC", "equal-weighted cosine", BLUE))
    panel = (("registered_two_way", "two-way\ncluster", VERMILLION),
             ("WCR", "wild\nbootstrap", ORANGE),
             ("IM", "Ibragimov-\nMüller", BLUE))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.3), layout="constrained",
                                   gridspec_kw={"width_ratios": [3, 1.5]})
    lengths = [17, 18, 28]
    for j, (key, label, color) in enumerate(monthly):
        rates = [[100 * c["procedures"][key]["levels"]["0.05"]["rate"] for c in cal["case_results"]
                  if c["kind"] == "monthly_null" and c["T"] == t] for t in lengths]
        for i, rs in enumerate(rates):
            x = i + (j - 1) * 0.27
            ax1.bar(x, sum(rs) / len(rs), width=0.25, color=color, alpha=0.9,
                    label=label if i == 0 else None)
            ax1.scatter([x] * len(rs), rs, s=12, color=T["ink"], zorder=3)
    ax1.legend(frameon=False, fontsize=9, loc="upper right")
    ax1.axhline(5, color=T["ink"], ls="--", lw=1)
    ax1.text(-0.45, 6, "should be 5%", fontsize=9)
    ax1.set_xticks(range(len(lengths)), [f"{t} months" for t in lengths])
    ax1.set_ylabel("false-positive rate, %")
    ax1.set_title("monthly alpha test, 6 factor controls", fontsize=10.5)
    ax1.grid(axis="x", visible=False)
    for j, (key, label, color) in enumerate(panel):
        rates = [100 * c["procedures"][key]["levels"]["0.05"]["rate"] for c in cal["case_results"]
                 if c["kind"] == "panel_null"]
        ax2.bar(j, sum(rates) / len(rates), color=color, width=0.6, alpha=0.9)
        ax2.scatter([j] * len(rates), rates, s=12, color=T["ink"], zorder=3)
    ax2.axhline(5, color=T["ink"], ls="--", lw=1)
    ax2.set_xticks(range(len(panel)), [p[1] for p in panel], fontsize=8.5)
    ax2.set_title("panel, 7 yearly clusters", fontsize=10.5)
    ax2.grid(axis="x", visible=False)
    _title(fig, "With 17-28 months of data, textbook tests find effects that are not there")
    return fig


def timestamps(theme: str):
    """SEC acceptance-time disagreement between two official SEC JSON sources."""
    audit = _load("p0_acceptance_authority_audit.json")
    char = audit["full_H0_disagreement_characterization"]
    auth = audit["authority_summary"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.9), layout="constrained",
                                   gridspec_kw={"width_ratios": [1.2, 1]})
    counts = char["offset_counts"]
    labels = ["exactly 4 h later\n(daylight time)", "exactly 5 h later\n(standard time)",
              "any other gap"]
    values = [counts["4.0"], counts["5.0"], char["differences"] - counts["4.0"] - counts["5.0"]]
    ax1.barh(labels[::-1], values[::-1], color=[T["muted"], VERMILLION, ORANGE])
    for y, v in enumerate(values[::-1]):
        ax1.text(v + 2, y, str(v), va="center", fontsize=10)
    ax1.set_xlim(0, max(values) * 1.25)
    ax1.set_xlabel("filings where the bulk archive disagrees with the API")
    ax1.set_title(f"{char['differences']} of {char['rows']:,} filings disagree", fontsize=10.5)
    ax1.grid(axis="y", visible=False)
    n = auth["header_index_wall_matches"]
    bars = [auth["ET_header_matches_pair"], auth["ET_header_matches_bulk"]]
    ax2.bar(["API record", "bulk archive"], bars, color=[BLUE, ORANGE], width=0.55)
    for x, v in enumerate(bars):
        ax2.text(x, v + 0.4, f"{v} / {n}", ha="center", fontsize=10)
    ax2.set_ylim(0, n + 3)
    ax2.set_ylabel("agrees with the filing's\nown SEC header", labelpad=6)
    ax2.set_title("audited against the source of truth", fontsize=10.5)
    ax2.grid(axis="x", visible=False)
    _title(fig, "SEC's own timestamp feeds disagree by exactly one Eastern-time offset")
    return fig


def _wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def reader_accuracy(theme: str):
    """Local model on 30 TAT-QA questions, each asked with and without its report."""
    items = _load("reader_real2_combined.json")["items"]

    def tally(rows, arm):
        return sum(r[arm]["outcome"] == "correct" for r in rows), len(rows)

    by_type = {t: [r for r in items if r["answer_type"] == t]
               for t in ("span", "arithmetic", "multi-span")}
    rows = [("all questions, report given", *tally(items, "report_supplied"), BLUE, True),
            ("all questions, no report", *tally(items, "no_report"), VERMILLION, True)]
    rows += [(f"{t}, report given", *tally(r, "report_supplied"), BLUE, False)
             for t, r in by_type.items()]
    fig, ax = plt.subplots(figsize=(10.5, 3.9), layout="constrained")
    for y, (label, k, n, color, bold) in enumerate(rows[::-1]):
        lo, hi = _wilson(k, n)
        ax.plot([100 * lo, 100 * hi], [y, y], color=color, lw=2.5, alpha=0.45,
                solid_capstyle="round")
        ax.scatter([100 * k / n], [y], s=60, color=color, zorder=3)
        ax.text(100 * hi + 1.5, y, f"{k} / {n}", va="center", fontsize=10,
                fontweight="bold" if bold else "normal")
    labels = [r[0] for r in rows[::-1]]
    ax.set_yticks(range(len(rows)), labels)
    ax.axhline(2.5, color=T["grid"], lw=1)
    ax.axvline(84.1, color=T["muted"], ls="--", lw=1)
    ax.text(83, len(rows) - 0.45, "human experts, paper's test set: 84%", ha="right",
            va="center", fontsize=9, color=T["muted"])
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, len(rows) - 0.2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlabel("exactly right (dot) with 95% range (bar)")
    ax.grid(axis="y", visible=False)
    _title(fig, "A small local model answers from the report, not from memory, "
                "but often gets calculations wrong")
    return fig


FIGURES = {
    "time-machine": time_machine,
    "development-returns": development_returns,
    "leak-probe": leak_probe,
    "test-size": test_size,
    "timestamps": timestamps,
    "reader-accuracy": reader_accuracy,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        _use_theme(theme)
        for name, build in FIGURES.items():
            fig = build(theme)
            fig.savefig(OUT / f"{name}-{theme}.svg", metadata={"Date": None})
            plt.close(fig)
    print(f"wrote {len(FIGURES) * len(THEMES)} figures to {OUT}")


if __name__ == "__main__":
    main()

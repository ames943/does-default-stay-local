"""Publication versions of the seven paper charts.

Reuses the chart builders in build_yield_charts, compare_city_vs_state,
compare_city_vs_state_cincinnati_pittsburgh and compare_canal_robustness on the
CSVs in output/, so the plotted data is the same. Figure.savefig is redirected
into figures/ and the cosmetic edits are made on the figure just before it is
saved:

- figure titles, panel titles (except the two short canal panel labels) and the
  footnote block are removed, since the paper's captions replace them;
- asterisks are removed and line labels are cut to the plain state or city name;
- the Indiana panel legend reads "Paid first" / "Paid second";
- the New York canal legend shows a single "New York" entry;
- date axes spanning under 6 years get yearly ticks.

Each chart is written to figures/ as a PNG (300 dpi) and a PDF under the name the
paper uses (fig1_canal_bonds through fig7_cincinnati_vs_ohio, see FIG_NAMES).

Run from anywhere after the rest of the pipeline has produced output/*.csv.
"""

import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.figure  # noqa: E402
import pandas as pd  # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT / "scripts"
OUTPUT = PROJECT / "output"
FINAL = PROJECT / "figures"

sys.path.insert(0, str(SCRIPTS))
import build_yield_charts as byc  # noqa: E402
import compare_city_vs_state as cvs  # noqa: E402
import compare_city_vs_state_cincinnati_pittsburgh as cip  # noqa: E402
import compare_canal_robustness as canal  # noqa: E402

# Name each chart builder saves under -> name the paper uses.
FIG_NAMES = {
    "chart_canal_robustness": "fig1_canal_bonds",
    "chart_panic_window": "fig2_states_panic",
    "chart_policy_short_medium": "fig3_states_after_signal",
    "chart_policy_long_term": "fig4_ohio_alabama_long_run",
    "chart_city_vs_state": "fig5_philadelphia_vs_pennsylvania",
    "chart_pittsburgh_vs_pa": "fig6_pittsburgh_vs_pennsylvania",
    "chart_cincinnati_vs_ohio": "fig7_cincinnati_vs_ohio",
}
PANEL_TITLES = {
    "New York Canal Bonds (secondary/robustness)": "New York canal bonds",
    "Indiana Butler Bill Tranches: Preferred vs. Deferred": "Indiana: bonds paid first vs. second",
}
LEGEND_MAP = {
    "Preferred (S-0490 + S-0500)": "Paid first",
    "Deferred (S-0480 + S-0506)": "Paid second",
}
STATE_NAMES = r"(Pennsylvania|Philadelphia|Ohio|Alabama|Indiana|New York|Cincinnati|Pittsburgh)"
STATE_LABEL_RE = re.compile(rf"^{STATE_NAMES} \([^)]*\)(\n.*)?$", re.DOTALL)
NY_CANAL_LABEL_RE = re.compile(r"^S-\d{4} \(New York")
# Right-edge labels that collide in the short/medium policy chart get nudged apart (points).
LABEL_NUDGE = {"Alabama": 9, "Ohio": -9}
# Date-axis tick spacing (years) for charts whose default yearly ticks run together.
TICK_EVERY = {"chart_cincinnati_vs_ohio": 5}

_orig_savefig = matplotlib.figure.Figure.savefig


def plain_label(text: str) -> str:
    # Keeps a second line such as "(ends Dec 1848)" under the bare state name.
    text = text.replace("*", "")
    m = STATE_LABEL_RE.match(text)
    return m.group(1) + (m.group(2) or "") if m else text


def clean_figure(fig, stem: str) -> None:
    # Captions and the figure-level title go; the LaTeX caption replaces them.
    for t in list(fig.texts):
        t.remove()
    fig._suptitle = None

    for ax in fig.axes:
        for loc in ("left", "center", "right"):
            title = ax.get_title(loc=loc)
            if title:
                ax.set_title(PANEL_TITLES.get(title, ""), loc=loc)
        ax.set_ylabel(ax.get_ylabel().replace(" -- see note", ""))
        for t in ax.texts:
            t.set_text(plain_label(t.get_text()))
            name = t.get_text().split(" ")[0].split("\n")[0]
            if stem == "chart_policy_short_medium" and name in LABEL_NUDGE:
                x, y = t.xyann
                t.xyann = (x, y + LABEL_NUDGE[name])
        # A lone data point has no line segment to draw, so give it a marker.
        for line in ax.lines:
            if len(line.get_xdata()) == 1:
                line.set_marker("o")
                line.set_markersize(5)

        leg = ax.get_legend()
        if leg is not None:
            size = leg.get_texts()[0].get_fontsize()
            handles, labels = ax.get_legend_handles_labels()
            new_h, new_l, seen = [], [], set()
            for h, label in zip(handles, labels):
                if label in LEGEND_MAP:
                    new = LEGEND_MAP[label]
                elif NY_CANAL_LABEL_RE.match(label):
                    new = "New York"
                else:
                    new = plain_label(label)
                if new in seen:
                    continue
                seen.add(new)
                new_h.append(h)
                new_l.append(new)
            ax.legend(new_h, new_l, fontsize=size, loc="upper right", frameon=False)

        if isinstance(ax.xaxis.get_major_formatter(), mdates.DateFormatter):
            lo, hi = ax.get_xlim()
            span_years = (hi - lo) / 365.25
            if span_years < 6:
                ax.xaxis.set_major_locator(mdates.YearLocator(1))


def final_savefig(self, fname, *args, **kwargs):
    stem = Path(str(fname)).stem
    clean_figure(self, stem)
    if stem in TICK_EVERY:
        for ax in self.axes:
            if isinstance(ax.xaxis.get_major_formatter(), mdates.DateFormatter):
                ax.xaxis.set_major_locator(mdates.YearLocator(TICK_EVERY[stem], month=1, day=1))
    self.tight_layout()
    base = FINAL / FIG_NAMES[stem]
    _orig_savefig(self, base.with_suffix(".png"), dpi=300, facecolor=self.get_facecolor())
    _orig_savefig(self, base.with_suffix(".pdf"), facecolor=self.get_facecolor())
    print(f"saved -> {base}.png / .pdf")


def main() -> None:
    matplotlib.figure.Figure.savefig = final_savefig

    df = byc.load_usable()
    byc.build_chart_1(df)  # chart_panic_window
    byc.build_chart_2(df)  # chart_policy_short_medium
    byc.build_chart_3(df)  # chart_policy_long_term

    cvs_df = pd.read_csv(OUTPUT / "city_vs_state_yields.csv", parse_dates=["date"])
    cvs.build_chart(cvs_df)  # chart_city_vs_state

    pit = pd.read_csv(OUTPUT / "city_vs_state_pittsburgh.csv", parse_dates=["date"])
    cip.build_chart("Pittsburgh", pit)  # chart_pittsburgh_vs_pa

    cin = pd.read_csv(OUTPUT / "city_vs_state_cincinnati.csv", parse_dates=["date"])
    cip.build_chart("Cincinnati", cin)  # chart_cincinnati_vs_ohio

    robustness = pd.read_csv(OUTPUT / "canal_robustness_yields.csv", parse_dates=["date"])
    canal.build_chart(robustness[robustness.state == "New York"], robustness[robustness.state == "Indiana"])

    print("done")


if __name__ == "__main__":
    main()

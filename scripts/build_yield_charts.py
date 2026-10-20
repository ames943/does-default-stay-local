"""Build the three yield comparison charts.

1. Panic window (1835 to 1845): all five states, all primary bonds.
2. Policy window, short and medium term (Apr 1843 onward): all five states, each
   cut off where its own usable data ends rather than at a shared date.
3. Policy window, long term (through the 1850s): Ohio (S-2110, S-2080) and
   Alabama (S-0030) only, the two series with dense coverage that long.
   Pennsylvania, Indiana and New York do not have it.

A state's yield on a given date is the mean of the yield column across its
bonds with a usable (non-excluded) quote that day. That is YTM for
Pennsylvania, Ohio and New York, and current yield for Alabama and Indiana,
which have no usable maturity date. Each chart says so in its footnote.

Colors are fixed by state across all three charts: Pennsylvania blue, Ohio
green, Alabama magenta, Indiana yellow, New York aqua.
"""

import textwrap
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

SURFACE = "#fcfcfb"
PRIMARY_TEXT = "#0b0b0b"
SECONDARY_TEXT = "#52514e"
MUTED_TEXT = "#898781"
GRID_COLOR = "#e1e0d9"
AXIS_COLOR = "#c3c2b7"
SIGNAL_COLOR = "#e34948"

STATE_COLOR = {
    "Pennsylvania": "#2a78d6",
    "Ohio": "#008300",
    "Alabama": "#e87ba4",
    "Indiana": "#eda100",
    "New York": "#1baf7a",
}
STATE_BUCKET = {
    "Pennsylvania": "defaulted",
    "Ohio": "safe",
    "Alabama": "risky, survived",
    "Indiana": "defaulted",
    "New York": "risky, survived",
}
NY_DATA_NOTE = (
    "New York (S-1650) data begin in Jul 1842, so New York's credit risk before then cannot be seen in this series."
)

PANIC_START = pd.Timestamp("1835-01-01")
PANIC_END = pd.Timestamp("1845-12-31")
POLICY_SIGNAL = pd.Timestamp("1843-04-01")
PA_DEFAULT = pd.Timestamp("1842-08-01")


def load_usable() -> pd.DataFrame:
    df = pd.read_csv(OUTPUT_DIR / "primary_yields.csv", parse_dates=["date"])
    df = df[(df.series_label == "primary") & ~df.excluded_past_maturity & ~df.excluded_near_maturity]
    return df


def state_series(df: pd.DataFrame, state: str, codes: list, date_min=None, date_max=None) -> pd.Series:
    sub = df[(df.state == state) & df.code.isin(codes)]
    if date_min is not None:
        sub = sub[sub.date >= date_min]
    if date_max is not None:
        sub = sub[sub.date <= date_max]
    return sub.groupby("date")["yield"].mean().sort_index()


def new_fig():
    fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color(AXIS_COLOR)
    ax.tick_params(colors=MUTED_TEXT, labelsize=9)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    return fig, ax


def draw_series(ax, s: pd.Series, state: str, label_suffix: str = ""):
    if s.empty:
        return
    color = STATE_COLOR[state]
    bucket = STATE_BUCKET[state]
    ax.plot(s.index, s.values, color=color, linewidth=2, solid_capstyle="round")
    end_x, end_y = s.index[-1], s.values[-1]
    ax.annotate(
        f"{state} ({bucket}){label_suffix}",
        xy=(end_x, end_y),
        xytext=(6, 0),
        textcoords="offset points",
        color=color,
        fontsize=9,
        fontweight="bold",
        va="center",
        ha="left",
    )


def add_signal_line(ax, date: pd.Timestamp, label: str):
    ax.axvline(date, color=SIGNAL_COLOR, linestyle="--", linewidth=1.3)
    ax.annotate(
        label,
        xy=(date, ax.get_ylim()[1]),
        xytext=(6, -6),
        textcoords="offset points",
        color=SIGNAL_COLOR,
        fontsize=9,
        fontweight="bold",
        va="top",
        ha="left",
    )


def finish(fig, ax, title: str, methodology_note: str, out_name: str):
    ax.set_xlabel("Date", color=PRIMARY_TEXT, fontsize=11)
    ax.set_ylabel("Yield (%)", color=PRIMARY_TEXT, fontsize=11)
    ax.set_title(title, color=PRIMARY_TEXT, fontsize=13, fontweight="bold", loc="left")

    wrapped_lines = []
    for paragraph in methodology_note.split("\n"):
        wrapped_lines.extend(textwrap.wrap(paragraph, width=155) or [""])
    wrapped = "\n".join(wrapped_lines)

    fig.text(0.01, 0.01, wrapped, color=SECONDARY_TEXT, fontsize=8, ha="left", va="bottom")
    bottom_margin = 0.02 + 0.018 * len(wrapped_lines)
    fig.tight_layout(rect=(0, bottom_margin, 1, 1))
    out_path = OUTPUT_DIR / out_name
    fig.savefig(out_path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"saved -> {out_path}")


PA_CODES = ["S-2240", "S-2250", "S-2270", "S-2330", "S-2410"]
OHIO_ALL = ["S-2100", "S-2110", "S-2080", "S-2010"]
OHIO_LONG = ["S-2110", "S-2080"]
ALABAMA_ALL = ["S-0030", "S-0040"]
ALABAMA_LONG = ["S-0030"]
INDIANA_CODES = ["S-0510", "S-0540"]
NY_CODES = ["S-1650"]

METHOD_NOTE = (
    "Yield = mean across each state's usable primary bonds per date. YTM (approx.) for Pennsylvania/Ohio/New York; "
    "current yield for Alabama/Indiana (no usable maturity data) and for any state during its own active-default "
    "period (PA Aug 1842-Feb 1845, Indiana from Jan 1841)."
)


def build_chart_1(df: pd.DataFrame):
    fig, ax = new_fig()
    for state, codes in [
        ("Pennsylvania", PA_CODES),
        ("Ohio", OHIO_ALL),
        ("Alabama", ALABAMA_ALL),
        ("Indiana", INDIANA_CODES),
        ("New York", NY_CODES),
    ]:
        s = state_series(df, state, codes, PANIC_START, PANIC_END)
        draw_series(ax, s, state)
    add_signal_line(ax, PA_DEFAULT, "PA Default\n(Aug 1842)")
    finish(
        fig, ax,
        "Panic-Window Yields, 1835–1845 — All 5 States",
        METHOD_NOTE + " Window: panic/default shock (1835-1845), not the policy signal.\n" + NY_DATA_NOTE,
        "chart_panic_window.png",
    )


def build_chart_2(df: pd.DataFrame):
    fig, ax = new_fig()
    for state, codes in [
        ("Pennsylvania", PA_CODES),
        ("Ohio", OHIO_ALL),
        ("Alabama", ALABAMA_ALL),
        ("Indiana", INDIANA_CODES),
        ("New York", NY_CODES),
    ]:
        s = state_series(df, state, codes, POLICY_SIGNAL, None)
        end_note = f"\n(ends {s.index[-1].strftime('%b %Y')})" if len(s) else ""
        draw_series(ax, s, state, label_suffix=end_note)
    add_signal_line(ax, POLICY_SIGNAL, "No-bailout signal\n(Apr 1843)")
    finish(
        fig, ax,
        "Policy-Window Yields, Short/Medium-Term — Each State to Its Own Coverage Ceiling",
        METHOD_NOTE + " Lines end where each state's usable data ends -- not a shared cutoff; see per-line labels.\n"
        + NY_DATA_NOTE,
        "chart_policy_short_medium.png",
    )


def build_chart_3(df: pd.DataFrame):
    fig, ax = new_fig()
    for state, codes in [("Ohio", OHIO_LONG), ("Alabama", ALABAMA_LONG)]:
        s = state_series(df, state, codes, POLICY_SIGNAL, None)
        draw_series(ax, s, state)
    add_signal_line(ax, POLICY_SIGNAL, "No-bailout signal\n(Apr 1843)")
    finish(
        fig, ax,
        "Policy-Window Yields, Long-Term — Ohio (safe) vs. Alabama (risky, survived) Only, through the 1850s",
        METHOD_NOTE + " Restricted to Ohio (S-2110, S-2080) and Alabama (S-0030), the only two series with "
        "dense coverage this long. Alabama is a state that survived without defaulting, so the chart shows "
        "whether its yield converges toward the safe state's over time.",
        "chart_policy_long_term.png",
    )


def main():
    df = load_usable()
    build_chart_1(df)
    build_chart_2(df)
    build_chart_3(df)


if __name__ == "__main__":
    main()

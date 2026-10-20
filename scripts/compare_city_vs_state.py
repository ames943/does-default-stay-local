"""Philadelphia (city) vs. Pennsylvania (state) yield comparison.

Covers this one city/state pair only. Cincinnati and Pittsburgh are handled in
compare_city_vs_state_cincinnati_pittsburgh.py.

Data
----
Philadelphia's bond (C-1100, "Philadelphia 5s, r. 1846") is on the "Municipal
Debt" sheet of Philadelphia1.xls, which parse_securities.py does not read (it
only parses "U.S. and State Debt"). This script parses that sheet directly the
same way: paired code/code+"a" columns and "year.monthday" float dates.

C-1100 has a 343-day gap, Feb 25 1843 to Feb 3 1844, so the Apr 1843
no-bailout signal falls inside it and the city's immediate reaction cannot be
observed. The chart draws the gap as a dotted segment, and the pre/post spreads
printed below use windows that avoid it. The second Philadelphia bond (C-1260,
see output/checks/philadelphia_second_bond_check.csv) has quotes during the gap.

Yield measure
-------------
Both sides use current yield (coupon / price). Pennsylvania's primary series
uses yield to maturity by default, but all of its post-signal observations
(S-2330, S-2410, Dec 1842 to Jan 1845) fall inside its active-default window
(Aug 1842 to Feb 1845), where calculate_yields.py already switches to current
yield. Using current yield for Philadelphia as well keeps the two on the same
measure.

C-1100 never gets near its 1846 maturity within its observed window (last
quote Dec 1844), so no maturity truncation applies. Its price shows no default
pattern (a dip to 91-94 in late 1842 and early 1843, back above 100 by 1844)
and I found no record of a city-level suspension, so the active-default
override is not applied to it.

Outputs
-------
- output/city_vs_state_yields.csv
- output/chart_city_vs_state.png
"""

import textwrap
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import xlrd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

PHILADELPHIA_XLS = RAW_DIR / "Philadelphia1.xls"
MUNICIPAL_SHEET = "Municipal Debt"
CITY_CODE = "C-1100"
CITY_COUPON = 5.0  # "Philadelphia 5s, r. 1846" (Securities Index.xls)

GAP_START = pd.Timestamp("1843-02-25")  # C-1100's last obs before the gap
GAP_END = pd.Timestamp("1844-02-03")  # C-1100's first obs after the gap
SIGNAL = pd.Timestamp("1843-04-01")  # no-bailout signal (falls inside the gap)
PA_DEFAULT = pd.Timestamp("1842-08-01")

SURFACE = "#fcfcfb"
PRIMARY_TEXT = "#0b0b0b"
SECONDARY_TEXT = "#52514e"
MUTED_TEXT = "#898781"
GRID_COLOR = "#e1e0d9"
AXIS_COLOR = "#c3c2b7"
SIGNAL_COLOR = "#e34948"
DEFAULT_COLOR = "#9a6b00"
STATE_COLOR = "#2a78d6"  # Pennsylvania, same blue as build_yield_charts.py
CITY_COLOR = "#7a3fc9"  # Philadelphia, not reused from the state palette


def excel_year_monthday_to_datetime(series: pd.Series) -> pd.Series:
    """Convert a 'year.monthday' float (e.g. 1841.0807) to a datetime.

    Same convention as parse_securities.py: integer part is the year,
    fractional part read as a 4-digit zero-padded number is month+day.
    """
    as_str = series.astype(float).map(lambda v: f"{v:.4f}")
    year = as_str.str.slice(0, 4)
    month_day = as_str.str.split(".").str[1].str.ljust(4, "0")
    month = month_day.str.slice(0, 2)
    day = month_day.str.slice(2, 4)
    date_str = year + month + day
    return pd.to_datetime(date_str, format="%Y%m%d", errors="coerce")


def load_city_price_series() -> pd.Series:
    wb = xlrd.open_workbook(PHILADELPHIA_XLS)
    sh = wb.sheet_by_name(MUNICIPAL_SHEET)
    header = sh.row_values(0)
    rows = [sh.row_values(r) for r in range(1, sh.nrows)]
    df = pd.DataFrame(rows, columns=header)
    dates = excel_year_monthday_to_datetime(df[df.columns[0]])
    price = pd.to_numeric(df[CITY_CODE].replace("", pd.NA), errors="coerce")
    price.index = dates
    return price.dropna().sort_index()


def load_state_yield_series() -> pd.Series:
    """PA's primary series from primary_yields.csv, maturity exclusions applied."""
    df = pd.read_csv(OUTPUT_DIR / "primary_yields.csv", parse_dates=["date"])
    df = df[
        (df.state == "Pennsylvania")
        & (df.series_label == "primary")
        & ~df.excluded_past_maturity
        & ~df.excluded_near_maturity
    ]
    return df.groupby("date")["yield"].mean().sort_index()


def build_comparison_frame(city_price: pd.Series, pa_state: pd.DataFrame) -> pd.DataFrame:
    city_yield = CITY_COUPON / city_price * 100
    city_out = pd.DataFrame(
        {
            "date": city_price.index,
            "level": "city",
            "entity": "Philadelphia",
            "state": "Philadelphia",
            "code": CITY_CODE,
            "price": city_price.values,
            "coupon": CITY_COUPON,
            "yield_measure_used": "current_yield",
            "yield": city_yield.values,
            "current_yield": city_yield.values,
            "bucket": "no_default_confirmed",
            "excluded_near_maturity": False,
            "excluded_past_maturity": False,
        }
    )

    pa_out = pa_state.copy()
    pa_out["level"] = "state"
    pa_out["entity"] = "Pennsylvania"

    cols = [
        "date", "level", "entity", "state", "code", "price", "coupon",
        "yield_measure_used", "yield", "current_yield", "bucket",
        "excluded_near_maturity", "excluded_past_maturity",
    ]
    return pd.concat([pa_out[cols], city_out[cols]], ignore_index=True).sort_values(["level", "date"])


def print_spread_summary(city_price: pd.Series, pa_yield_by_date: pd.Series) -> None:
    city_yield = CITY_COUPON / city_price * 100
    matched_start = city_yield.index.min()

    pa_pre = pa_yield_by_date[(pa_yield_by_date.index >= matched_start) & (pa_yield_by_date.index < SIGNAL)]
    city_pre = city_yield[(city_yield.index >= matched_start) & (city_yield.index < SIGNAL)]
    print(f"Matched pre-signal window ({matched_start.date()} to {SIGNAL.date()}):")
    print(f"  Pennsylvania (state): mean {pa_pre.mean():.2f}%  n={len(pa_pre)}")
    print(f"  Philadelphia (city):  mean {city_pre.mean():.2f}%  n={len(city_pre)}")
    print(f"  Spread: {pa_pre.mean() - city_pre.mean():.2f}pp")
    print()

    pa_overlap = pa_yield_by_date[(pa_yield_by_date.index >= GAP_END) & (pa_yield_by_date.index <= city_yield.index.max())]
    city_overlap = city_yield[(city_yield.index >= GAP_END) & (city_yield.index <= city_yield.index.max())]
    print(f"Post-gap overlap window ({GAP_END.date()} to {city_yield.index.max().date()}), apples-to-apples:")
    print(f"  Pennsylvania (state): mean {pa_overlap.mean():.2f}%  n={len(pa_overlap)}")
    print(f"  Philadelphia (city):  mean {city_overlap.mean():.2f}%  n={len(city_overlap)}")
    print(f"  Spread: {pa_overlap.mean() - city_overlap.mean():.2f}pp")
    print()

    gap_window = city_yield[(city_yield.index >= SIGNAL) & (city_yield.index < GAP_END)]
    print(f"Confirming the data gap: Philadelphia obs in {SIGNAL.date()}-{GAP_END.date()} = {len(gap_window)}")


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


def build_chart(comparison: pd.DataFrame) -> None:
    fig, ax = new_fig()

    pa = comparison[comparison.level == "state"].groupby("date")["yield"].mean().sort_index()
    ax.plot(pa.index, pa.values, color=STATE_COLOR, linewidth=2, solid_capstyle="round")
    ax.annotate(
        "Pennsylvania (state, defaulted)", xy=(pa.index[-1], pa.values[-1]), xytext=(6, 0),
        textcoords="offset points", color=STATE_COLOR, fontsize=9, fontweight="bold", va="center", ha="left",
    )

    city = comparison[comparison.level == "city"].set_index("date")["yield"].sort_index()
    seg1 = city[city.index <= GAP_START]
    seg2 = city[city.index >= GAP_END]
    ax.plot(seg1.index, seg1.values, color=CITY_COLOR, linewidth=2, solid_capstyle="round")
    ax.plot(seg2.index, seg2.values, color=CITY_COLOR, linewidth=2, solid_capstyle="round")
    ax.plot([GAP_START, GAP_END], [seg1.values[-1], seg2.values[0]], color=CITY_COLOR, linewidth=1, linestyle=":", alpha=0.6)
    ax.annotate(
        "Philadelphia (city, no default)", xy=(seg2.index[-1], seg2.values[-1]), xytext=(6, -10),
        textcoords="offset points", color=CITY_COLOR, fontsize=9, fontweight="bold", va="center", ha="left",
    )
    ax.annotate(
        "no data (343-day gap)", xy=(GAP_START, seg1.values[-1]), xytext=(0, 18), textcoords="offset points",
        color=CITY_COLOR, fontsize=7.5, ha="left", va="bottom", style="italic",
    )

    ax.axvline(PA_DEFAULT, color=DEFAULT_COLOR, linestyle="--", linewidth=1.3)
    ax.annotate(
        "PA Default\n(Aug 1842)", xy=(PA_DEFAULT, 0), xytext=(6, 6),
        textcoords="offset points", color=DEFAULT_COLOR, fontsize=9, fontweight="bold", va="bottom", ha="left",
    )

    ax.axvline(SIGNAL, color=SIGNAL_COLOR, linestyle="--", linewidth=1.3)
    ax.annotate(
        "No-bailout signal\n(Apr 1843)", xy=(SIGNAL, ax.get_ylim()[1]), xytext=(6, -6),
        textcoords="offset points", color=SIGNAL_COLOR, fontsize=9, fontweight="bold", va="top", ha="left",
    )

    ax.set_xlabel("Date", color=PRIMARY_TEXT, fontsize=11)
    ax.set_ylabel("Yield (%)", color=PRIMARY_TEXT, fontsize=11)
    ax.set_title(
        "City vs. State Yields, 1835-1845 -- Philadelphia (city) vs. Pennsylvania (state)",
        color=PRIMARY_TEXT, fontsize=13, fontweight="bold", loc="left",
    )

    method_note = (
        "Yield is current yield (coupon / price x 100) for both series, matching the measure Pennsylvania's own "
        "series uses during its active-default window (Aug 1842 to Feb 1845). Philadelphia (C-1100, "
        "\"Philadelphia 5s, r. 1846\") is far from maturity throughout and shows no default pattern, so no "
        "override is applied. C-1100 has a 343-day gap (Feb 1843 to Feb 1844, dotted), which covers nearly all of "
        "the period right after the Apr 1843 signal. This chart covers Philadelphia and Pennsylvania only."
    )
    wrapped_lines = []
    for paragraph in method_note.split("\n"):
        wrapped_lines.extend(textwrap.wrap(paragraph, width=155) or [""])
    wrapped = "\n".join(wrapped_lines)
    fig.text(0.01, 0.01, wrapped, color=SECONDARY_TEXT, fontsize=8, ha="left", va="bottom")
    bottom_margin = 0.02 + 0.018 * len(wrapped_lines)
    fig.tight_layout(rect=(0, bottom_margin, 1, 1))

    out_path = OUTPUT_DIR / "chart_city_vs_state.png"
    fig.savefig(out_path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"saved -> {out_path}")


def main() -> None:
    city_price = load_city_price_series()
    pa_state = pd.read_csv(OUTPUT_DIR / "primary_yields.csv", parse_dates=["date"])
    pa_state = pa_state[
        (pa_state.state == "Pennsylvania")
        & (pa_state.series_label == "primary")
        & ~pa_state.excluded_past_maturity
        & ~pa_state.excluded_near_maturity
    ]

    comparison = build_comparison_frame(city_price, pa_state)
    out_path = OUTPUT_DIR / "city_vs_state_yields.csv"
    comparison.to_csv(out_path, index=False)
    print(f"saved -> {out_path} ({len(comparison)} rows)")
    print()

    pa_yield_by_date = load_state_yield_series()
    print_spread_summary(city_price, pa_yield_by_date)
    print()

    build_chart(comparison)


if __name__ == "__main__":
    main()

"""Cincinnati vs. Ohio and Pittsburgh vs. Pennsylvania yield comparisons.

Extends compare_city_vs_state.py (Philadelphia vs. Pennsylvania) to the other
two city bonds on the "Municipal Debt" sheet of Philadelphia1.xls. Each city is
compared with its own state: Cincinnati with Ohio, Pittsburgh with
Pennsylvania.

Data
----
C-0436 ("Cincinnati 6s") and C-1394 ("Pittsburg 6s") are on the same sheet
C-1100 came from, parsed the same way as in compare_city_vs_state.py and
parse_securities.py (paired code/code+"a" columns, "year.monthday" float dates).

Coverage
--------
Neither city has a gap over 90 days (largest: C-0436 63 days, Aug to Oct 1848;
C-1394 63 days, Dec 1848 to Feb 1849). Unlike C-1100, though, both start
trading on Dec 31 1842 and have only 5 quotes before the Feb 11 1843 cutoff.
The pre-signal means are printed but are too thin to support a before/after
test. The comparison that matters is the level of the city yield against the
state yield after the signal: does the city trade persistently below its state,
as Philadelphia did, or move with it?

Quotes between Feb 11 and Apr 1 1843 belong to neither window.

Active default
--------------
No override is needed for either city. Ohio never defaulted in this episode.
I found no record of a Pittsburgh default separate from Pennsylvania's (Aug 1842
to Feb 1845), the same as for Philadelphia, and the C-1394 prices fit that: the
series opens depressed (75 to 80, like most bonds in 1842) and is back at
100 to 102 by 1844, nowhere near the state's fall to 37 to 40. This is by
analogy with Philadelphia and was not checked against a Pittsburgh-specific
source.

Yield measure
-------------
Neither city bond has a maturity year in Securities Index.xls, so both use
current yield (6.0 / price x 100) and no maturity truncation applies.

- Cincinnati vs. Ohio: Ohio's series from primary_yields.csv is mostly yield to
  maturity (Ohio has real maturity dates and no default period), so this pair
  compares current yield with YTM. The same mismatch exists for Alabama and
  Indiana in the main comparison.
- Pittsburgh vs. Pennsylvania: Pennsylvania's usable post-signal data
  (S-2330 and S-2410, through Jan 25 1845) all fall inside its default window,
  so it is already current yield and the two sides match.

Coverage ceilings
-----------------
- Cincinnati vs. Ohio: Ohio's series runs through Dec 1853, past Cincinnati's
  last quote (Dec 1850), so there is no ceiling.
- Pittsburgh vs. Pennsylvania: Pennsylvania's primary series ends Jan 25 1845
  while Pittsburgh trades through Dec 1850. The matched comparison stops at
  Jan 25 1845. Pittsburgh's own line is still drawn after that.

Outputs
-------
- output/city_vs_state_cincinnati.csv
- output/city_vs_state_pittsburgh.csv
- output/chart_cincinnati_vs_ohio.png
- output/chart_pittsburgh_vs_pa.png
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

SIGNAL = pd.Timestamp("1843-04-01")
PRE_SIGNAL_CUTOFF = pd.Timestamp("1843-02-11")
PA_DEFAULT = pd.Timestamp("1842-08-01")
PA_COVERAGE_CEILING = pd.Timestamp("1845-01-25")  # PA's own primary series ends here

SURFACE = "#fcfcfb"
PRIMARY_TEXT = "#0b0b0b"
SECONDARY_TEXT = "#52514e"
MUTED_TEXT = "#898781"
GRID_COLOR = "#e1e0d9"
AXIS_COLOR = "#c3c2b7"
SIGNAL_COLOR = "#e34948"
DEFAULT_COLOR = "#9a6b00"
STATE_COLOR = "#2a78d6"
CITY_COLOR = "#1f9e6d"  # not reused from Philadelphia (#7a3fc9)

CITY_SPECS = {
    "Cincinnati": {
        "code": "C-0436",
        "coupon": 6.0,
        "state": "Ohio",
        "coverage_ceiling": None,  # Ohio's own series stays dense through 1853
        "out_csv": "city_vs_state_cincinnati.csv",
        "out_chart": "chart_cincinnati_vs_ohio.png",
        "yield_parity_note": (
            "Ohio's series is mostly yield to maturity (Ohio never defaulted, so no default "
            "override applies). Cincinnati is current yield because the codebook has no maturity "
            "date, so the two measures differ, as they do for Alabama and Indiana."
        ),
    },
    "Pittsburgh": {
        "code": "C-1394",
        "coupon": 6.0,
        "state": "Pennsylvania",
        "coverage_ceiling": PA_COVERAGE_CEILING,
        "out_csv": "city_vs_state_pittsburgh.csv",
        "out_chart": "chart_pittsburgh_vs_pa.png",
        "yield_parity_note": (
            "Pennsylvania's usable post-signal data (through Jan 25 1845) fall entirely inside its "
            "default period, so they are already current yield and both sides use the same measure."
        ),
    },
}


def excel_year_monthday_to_datetime(series: pd.Series) -> pd.Series:
    as_str = series.astype(float).map(lambda v: f"{v:.4f}")
    year = as_str.str.slice(0, 4)
    month_day = as_str.str.split(".").str[1].str.ljust(4, "0")
    month = month_day.str.slice(0, 2)
    day = month_day.str.slice(2, 4)
    date_str = year + month + day
    return pd.to_datetime(date_str, format="%Y%m%d", errors="coerce")


def load_municipal_sheet() -> pd.DataFrame:
    wb = xlrd.open_workbook(PHILADELPHIA_XLS)
    sh = wb.sheet_by_name(MUNICIPAL_SHEET)
    header = sh.row_values(0)
    rows = [sh.row_values(r) for r in range(1, sh.nrows)]
    df = pd.DataFrame(rows, columns=header)
    df.index = excel_year_monthday_to_datetime(df[df.columns[0]])
    return df


def load_city_price_series(sheet_df: pd.DataFrame, code: str) -> pd.Series:
    price = pd.to_numeric(sheet_df[code].replace("", pd.NA), errors="coerce")
    price.index = sheet_df.index
    return price.dropna().sort_index()


def load_state_yield_series(state: str) -> pd.Series:
    """Reuses the state's existing primary series as-is from
    primary_yields.csv -- never recomputed, per instructions not to touch
    calculate_yields.py or primary_yields.csv."""
    df = pd.read_csv(OUTPUT_DIR / "primary_yields.csv", parse_dates=["date"])
    df = df[
        (df.state == state)
        & (df.series_label == "primary")
        & ~df.excluded_past_maturity
        & ~df.excluded_near_maturity
    ]
    return df.groupby("date")["yield"].mean().sort_index()


def build_comparison_frame(city_price: pd.Series, coupon: float, city_name: str,
                            state: str, state_df: pd.DataFrame) -> pd.DataFrame:
    city_yield = coupon / city_price * 100
    city_out = pd.DataFrame(
        {
            "date": city_price.index,
            "level": "city",
            "entity": city_name,
            "state": city_name,
            "code": CITY_SPECS[city_name]["code"],
            "price": city_price.values,
            "coupon": coupon,
            "yield_measure_used": "current_yield",
            "yield": city_yield.values,
            "current_yield": city_yield.values,
            "bucket": "no_default_confirmed",
            "excluded_near_maturity": False,
            "excluded_past_maturity": False,
        }
    )

    state_out = state_df.copy()
    state_out["level"] = "state"
    state_out["entity"] = state

    cols = [
        "date", "level", "entity", "state", "code", "price", "coupon",
        "yield_measure_used", "yield", "current_yield", "bucket",
        "excluded_near_maturity", "excluded_past_maturity",
    ]
    return pd.concat([state_out[cols], city_out[cols]], ignore_index=True).sort_values(["level", "date"])


def print_spread_summary(city_name: str, city_yield: pd.Series, state_yield_by_date: pd.Series) -> None:
    spec = CITY_SPECS[city_name]
    state = spec["state"]
    ceiling = spec["coverage_ceiling"]

    pre_city = city_yield[city_yield.index < PRE_SIGNAL_CUTOFF]
    pre_state = state_yield_by_date[
        (state_yield_by_date.index >= city_yield.index.min()) & (state_yield_by_date.index < PRE_SIGNAL_CUTOFF)
    ]
    print(f"=== {city_name} vs. {state} ===")
    print(f"Pre-signal window ({city_yield.index.min().date()} to {PRE_SIGNAL_CUTOFF.date()}) "
          f"-- thin, n={len(pre_city)} city obs:")
    print(f"  {state} (state): mean {pre_state.mean():.2f}%  n={len(pre_state)}")
    print(f"  {city_name} (city): mean {pre_city.mean():.2f}%  n={len(pre_city)}")
    print()

    post_end = ceiling if ceiling is not None else city_yield.index.max()
    post_city = city_yield[(city_yield.index >= SIGNAL) & (city_yield.index <= post_end)]
    post_state = state_yield_by_date[(state_yield_by_date.index >= SIGNAL) & (state_yield_by_date.index <= post_end)]
    ceiling_note = f" (capped at {state}'s own coverage ceiling, {post_end.date()})" if ceiling is not None else ""
    print(f"Post-signal window ({SIGNAL.date()} to {post_end.date()}){ceiling_note}, main comparison:")
    print(f"  {state} (state): mean {post_state.mean():.2f}%  n={len(post_state)}")
    print(f"  {city_name} (city): mean {post_city.mean():.2f}%  n={len(post_city)}")
    print(f"  Spread (state - city): {post_state.mean() - post_city.mean():.2f}pp")
    print()


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


def build_chart(city_name: str, comparison: pd.DataFrame) -> None:
    spec = CITY_SPECS[city_name]
    state = spec["state"]
    fig, ax = new_fig()

    state_series = comparison[comparison.level == "state"].groupby("date")["yield"].mean().sort_index()
    ax.plot(state_series.index, state_series.values, color=STATE_COLOR, linewidth=2, solid_capstyle="round")
    ax.annotate(
        f"{state} (state)", xy=(state_series.index[-1], state_series.values[-1]), xytext=(6, 0),
        textcoords="offset points", color=STATE_COLOR, fontsize=9, fontweight="bold", va="center", ha="left",
    )

    city_series = comparison[comparison.level == "city"].set_index("date")["yield"].sort_index()
    ax.plot(city_series.index, city_series.values, color=CITY_COLOR, linewidth=2, solid_capstyle="round")
    ax.annotate(
        f"{city_name} (city, no default)", xy=(city_series.index[-1], city_series.values[-1]), xytext=(6, -10),
        textcoords="offset points", color=CITY_COLOR, fontsize=9, fontweight="bold", va="center", ha="left",
    )

    if state == "Pennsylvania":
        ax.axvline(PA_DEFAULT, color=DEFAULT_COLOR, linestyle="--", linewidth=1.3)
        ax.annotate(
            "PA Default\n(Aug 1842)", xy=(PA_DEFAULT, 0), xytext=(6, 6),
            textcoords="offset points", color=DEFAULT_COLOR, fontsize=9, fontweight="bold", va="bottom", ha="left",
        )
        ax.axvline(PA_COVERAGE_CEILING, color=MUTED_TEXT, linestyle=":", linewidth=1.1)
        y_mid = ax.get_ylim()[0] + 0.5 * (ax.get_ylim()[1] - ax.get_ylim()[0])
        ax.annotate(
            "PA state series\ncoverage ends", xy=(PA_COVERAGE_CEILING, y_mid), xytext=(6, 0),
            textcoords="offset points", color=MUTED_TEXT, fontsize=7.5, va="center", ha="left", style="italic",
        )

    ax.axvline(SIGNAL, color=SIGNAL_COLOR, linestyle="--", linewidth=1.3)
    ax.annotate(
        "No-bailout signal\n(Apr 1843)", xy=(SIGNAL, ax.get_ylim()[1]), xytext=(6, -6),
        textcoords="offset points", color=SIGNAL_COLOR, fontsize=9, fontweight="bold", va="top", ha="left",
    )

    ax.set_xlabel("Date", color=PRIMARY_TEXT, fontsize=11)
    ax.set_ylabel("Yield (%)", color=PRIMARY_TEXT, fontsize=11)
    ax.set_title(
        f"City vs. State Yields -- {city_name} (city) vs. {state} (state)",
        color=PRIMARY_TEXT, fontsize=13, fontweight="bold", loc="left",
    )

    method_note = (
        f"{city_name} ({spec['code']}, 6s, no maturity date in the codebook) is current yield "
        f"(coupon / price x 100). {spec['yield_parity_note']} "
        f"{city_name}'s pre-signal record is thin (5 quotes, Dec 31 1842 to Jan 28 1843, before the "
        "Feb 11 1843 cutoff), so this chart is read as a comparison of post-signal levels, not a "
        "before/after test. See chart_city_vs_state.png for Philadelphia and Pennsylvania."
    )
    wrapped_lines = []
    for paragraph in method_note.split("\n"):
        wrapped_lines.extend(textwrap.wrap(paragraph, width=155) or [""])
    wrapped = "\n".join(wrapped_lines)
    fig.text(0.01, 0.01, wrapped, color=SECONDARY_TEXT, fontsize=8, ha="left", va="bottom")
    bottom_margin = 0.02 + 0.018 * len(wrapped_lines)
    fig.tight_layout(rect=(0, bottom_margin, 1, 1))

    out_path = OUTPUT_DIR / spec["out_chart"]
    fig.savefig(out_path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"saved -> {out_path}")


def run_pair(city_name: str, sheet_df: pd.DataFrame) -> None:
    spec = CITY_SPECS[city_name]
    state = spec["state"]

    city_price = load_city_price_series(sheet_df, spec["code"])
    city_yield = spec["coupon"] / city_price * 100

    state_yields_raw = pd.read_csv(OUTPUT_DIR / "primary_yields.csv", parse_dates=["date"])
    state_df = state_yields_raw[
        (state_yields_raw.state == state)
        & (state_yields_raw.series_label == "primary")
        & ~state_yields_raw.excluded_past_maturity
        & ~state_yields_raw.excluded_near_maturity
    ]

    comparison = build_comparison_frame(city_price, spec["coupon"], city_name, state, state_df)
    out_path = OUTPUT_DIR / spec["out_csv"]
    comparison.to_csv(out_path, index=False)
    print(f"saved -> {out_path} ({len(comparison)} rows)")
    print()

    state_yield_by_date = load_state_yield_series(state)
    print_spread_summary(city_name, city_yield, state_yield_by_date)

    build_chart(city_name, comparison)
    print()


def main() -> None:
    sheet_df = load_municipal_sheet()
    for city_name in ["Cincinnati", "Pittsburgh"]:
        run_pair(city_name, sheet_df)


if __name__ == "__main__":
    main()

"""Robustness comparison using the canal (revenue-pledged) bonds.

The main comparison (calculate_yields.py) uses general-obligation bonds only.
This script covers the canal bonds that were set aside because of that choice:
New York Canal (S-1750, S-1820, S-1950) and the Indiana canal tranches created
by the 1847 Butler Bill (S-0480, S-0490, S-0500, S-0506).

Dropped bonds
-------------
- S-2190 (Ohio Canal 5s) has two price quotes, both from 1825, so there is
  nothing to plot for the 1840s and 1850s. Ohio is therefore absent here and the
  canal comparison covers two states, New York and Indiana.
- S-0470 (Indiana Canal) has no interest rate in the codebook, so no yield can
  be computed for it. Its trade density is still reported.

Yield measure (same rules as calculate_yields.py)
-------------------------------------------------
- New York canal bonds have maturity years in the codebook (1850, 1860, 1861)
  and New York has no default period, so they use yield to maturity with the
  usual exclusions (12-month near-maturity window, past-maturity dates).
- Indiana canal tranches have no maturity year, so they use current yield and
  no maturity exclusions apply. The active_default_override column is still
  filled in from Indiana's default period (open-ended from Jan 1 1841). Since
  the tranches only trade from 1850 on, every one of their rows is flagged True,
  even though the restructuring put the preferred tranche back on a paying
  basis. That comes from applying the Indiana default period mechanically; I
  did not special-case it.

Indiana preferred vs. deferred
------------------------------
Preferred is S-0490 (Preferred 5s) plus S-0500 (Special Preferred 5s). Deferred
is S-0480 (Deferred 5s) plus S-0506 (Special Deferred 5s). These trade from
1850 to 1853, well after the 1843 signal, so this test says nothing about the
signal. It asks whether the market priced the seniority difference that the
restructuring created.

Summary numbers used in the paper
---------------------------------
write_summary() saves output/canal_summary.csv with
- the New York canal mean yield from Apr 1 1843 onward, leaving out the S-1820
  price of 160.00 on 1848-10-14 (a transcription error), and
- the Indiana paid-first (preferred) and paid-second (deferred) comparison over
  the dates both are quoted, after dropping two unusual quotes: the S-0506 price
  of $1 on 1851-10-08 and the S-0480 price of $50 on 1850-09-21. The gap with
  each of the two quotes kept or dropped is saved as well, along with the number
  of months in which both groups are quoted and paid second yields more.

Outputs
-------
- output/canal_robustness_yields.csv
- output/canal_summary.csv
- output/chart_canal_robustness.png
"""

import textwrap
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import xlrd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
CODEBOOK_PATH = RAW_DIR / "Securities Index.xls"
NY_PRICES = OUTPUT_DIR / "new_york_state_debt_prices.csv"

FACE_VALUE = 100.0
NEAR_MATURITY_YEARS = 1.0
SIGNAL = pd.Timestamp("1843-04-01")
PRE_SIGNAL_CUTOFF = pd.Timestamp("1843-02-11")

# Indiana's default start date, same as DEFAULT_PERIODS in calculate_yields.py.
INDIANA_DEFAULT_START = pd.Timestamp("1841-01-01")

NY_CANAL_SPECS = [
    {"code": "S-1750", "name": "New York Canal 5s, 1850", "coupon": 5.0, "maturity": 1850},
    {"code": "S-1820", "name": "New York Canal 5s, 1860", "coupon": 5.0, "maturity": 1860},
    {"code": "S-1950", "name": "New York Canal 6s, 1861", "coupon": 6.0, "maturity": 1861},
]

INDIANA_CANAL_SPECS = [
    {"code": "S-0480", "name": "Indiana Canal Deferred 5s", "coupon": 5.0, "tranche": "deferred"},
    {"code": "S-0490", "name": "Indiana Canal Preferred 5s", "coupon": 5.0, "tranche": "preferred"},
    {"code": "S-0500", "name": "Indiana Canal Special Preferred 5s", "coupon": 5.0, "tranche": "preferred"},
    {"code": "S-0506", "name": "Indiana Canal Special Deferred 5s", "coupon": 5.0, "tranche": "deferred"},
]

DROPPED = {
    "S-2190": "Ohio Canal 5s -- 2 observations, both from 1825, nothing in the 1840s or 1850s. Dropped.",
    "S-0470": "Indiana Canal -- no interest rate in the codebook, so no yield. Left out of the yield "
              "comparison; trade density is reported only.",
}

# S-1750 has a 1,666-day gap in its quotes. Drawing a straight line across it would
# suggest a smooth climb from about 5% to 12% over four and a half years, so the gap is
# drawn as a dotted segment, as with C-1100 in compare_city_vs_state.py.
S1750_GAP_START = pd.Timestamp("1843-08-05")
S1750_GAP_END = pd.Timestamp("1848-02-26")

# S-1820 has a single price of 160.00 on 1848-10-14 between quotes of 96 to 99.5 either side.
# It is in the source file (New-York.xls, "NY State Debt" sheet, row 3256), so it is not a
# parsing error, but it is almost certainly a transcription error. It is left in
# canal_robustness_yields.csv and dropped from the chart line only.
S1820_ANOMALY_DATE = pd.Timestamp("1848-10-14")

# Two Indiana quotes left out of the headline paid-first / paid-second gap:
# S-0506 at $1 (a 500% current yield) and S-0480 at $50 (its first quote, far
# above every later one).
INDIANA_S0506_ODD_QUOTE = ("S-0506", pd.Timestamp("1851-10-08"))
INDIANA_S0480_ODD_QUOTE = ("S-0480", pd.Timestamp("1850-09-21"))

SURFACE = "#fcfcfb"
PRIMARY_TEXT = "#0b0b0b"
SECONDARY_TEXT = "#52514e"
MUTED_TEXT = "#898781"
GRID_COLOR = "#e1e0d9"
AXIS_COLOR = "#c3c2b7"
SIGNAL_COLOR = "#e34948"
NY_COLOR = "#2a78d6"
PREFERRED_COLOR = "#1f9e6d"
DEFERRED_COLOR = "#c9542c"


def load_codebook() -> dict:
    wb = xlrd.open_workbook(CODEBOOK_PATH)
    sh = wb.sheet_by_name("final")
    out = {}
    for r in range(1, sh.nrows):
        code, name, _type, interest, maturity = sh.row_values(r)
        out[code] = (name, interest, maturity)
    return out


def compute_ytm(price: pd.Series, coupon: float, n_years: pd.Series) -> pd.Series:
    return (coupon + (FACE_VALUE - price) / n_years) / ((FACE_VALUE + price) / 2) * 100


def build_ny_canal_frame(ny_df: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for spec in NY_CANAL_SPECS:
        price = ny_df[f"NY State Debt::{spec['code']}"].dropna().sort_index()
        coupon = spec["coupon"]
        maturity_date = pd.Timestamp(f"{spec['maturity']}-01-01")
        n_years = (maturity_date - price.index).days / 365.25
        excluded_past = n_years <= 0
        excluded_near = (n_years > 0) & (n_years <= NEAR_MATURITY_YEARS)

        ytm = compute_ytm(price, coupon, n_years)
        yield_value = ytm.where(~excluded_past, other=pd.NA)
        current_yield = coupon / price * 100

        frames.append(pd.DataFrame({
            "date": price.index,
            "state": "New York",
            "code": spec["code"],
            "name": spec["name"],
            "tranche": "n/a",
            "price": price.values,
            "coupon": coupon,
            "yield_measure_used": "ytm",
            "yield": yield_value.values,
            "current_yield": current_yield.values,
            "series_label": "canal_robustness",
            "excluded_near_maturity": pd.Series(excluded_near).values,
            "excluded_past_maturity": pd.Series(excluded_past).values,
            "active_default_override": False,  # New York never defaulted
        }))
    return pd.concat(frames, ignore_index=True)


def build_indiana_canal_frame(ny_df: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for spec in INDIANA_CANAL_SPECS:
        price = ny_df[f"Other State Debt::{spec['code']}"].dropna().sort_index()
        coupon = spec["coupon"]
        current_yield = coupon / price * 100
        default_override = price.index >= INDIANA_DEFAULT_START

        frames.append(pd.DataFrame({
            "date": price.index,
            "state": "Indiana",
            "code": spec["code"],
            "name": spec["name"],
            "tranche": spec["tranche"],
            "price": price.values,
            "coupon": coupon,
            "yield_measure_used": "current_yield",
            "yield": current_yield.values,
            "current_yield": current_yield.values,
            "series_label": "canal_robustness",
            "excluded_near_maturity": False,
            "excluded_past_maturity": False,
            "active_default_override": default_override,
        }))
    return pd.concat(frames, ignore_index=True)


def trade_density_report(ny_df: pd.DataFrame) -> None:
    print("=== Trade density, canal/robustness codes (including dropped/excluded) ===")
    all_codes = [s["code"] for s in NY_CANAL_SPECS] + [s["code"] for s in INDIANA_CANAL_SPECS] + list(DROPPED)
    sheets = {**{s["code"]: "NY State Debt" for s in NY_CANAL_SPECS},
              **{s["code"]: "Other State Debt" for s in INDIANA_CANAL_SPECS},
              "S-2190": "Other State Debt", "S-0470": "Other State Debt"}
    for code in all_codes:
        col = f"{sheets[code]}::{code}"
        s = ny_df[col].dropna().sort_index()
        status = f" -- {DROPPED[code]}" if code in DROPPED else ""
        if len(s) == 0:
            print(f"{code:8} n=0{status}")
            continue
        print(f"{code:8} n={len(s):4} range={s.index.min().date()} to {s.index.max().date()}{status}")
    print()


def usable_ny_canal_after_signal(ny_canal: pd.DataFrame) -> pd.DataFrame:
    df = ny_canal[~ny_canal.excluded_near_maturity & ~ny_canal.excluded_past_maturity]
    df = df[df.date >= SIGNAL]
    return df[~((df.code == "S-1820") & (df.date == S1820_ANOMALY_DATE))]


def indiana_overlap(indiana: pd.DataFrame):
    pref = indiana[indiana.tranche == "preferred"]
    defr = indiana[indiana.tranche == "deferred"]
    start = max(pref.date.min(), defr.date.min())
    end = min(pref.date.max(), defr.date.max())
    return (pref[(pref.date >= start) & (pref.date <= end)],
            defr[(defr.date >= start) & (defr.date <= end)])


def is_quote(df: pd.DataFrame, quote: tuple) -> pd.Series:
    return (df.code == quote[0]) & (df.date == quote[1])


def write_summary(ny_canal: pd.DataFrame, indiana: pd.DataFrame) -> None:
    rows = []

    ny = usable_ny_canal_after_signal(ny_canal)
    rows.append({"measure": "New York canal mean yield, Apr 1 1843 onward, S-1820 160.00 print excluded",
                 "group_a": ny["yield"].mean(), "n_a": len(ny), "group_b": None, "n_b": None, "gap": None})

    first, second = indiana_overlap(indiana)
    cases = [
        ("Indiana paid second minus paid first, both odd quotes dropped (headline)", True, True),
        ("Indiana, neither odd quote dropped", False, False),
        ("Indiana, only S-0480 $50 quote dropped", False, True),
        ("Indiana, only S-0506 $1 quote dropped", True, False),
    ]
    for label, drop_0506, drop_0480 in cases:
        keep = pd.Series(True, index=second.index)
        if drop_0506:
            keep &= ~is_quote(second, INDIANA_S0506_ODD_QUOTE)
        if drop_0480:
            keep &= ~is_quote(second, INDIANA_S0480_ODD_QUOTE)
        sec = second[keep]
        rows.append({"measure": label + " (group_a = paid second, group_b = paid first)",
                     "group_a": sec["yield"].mean(), "n_a": len(sec),
                     "group_b": first["yield"].mean(), "n_b": len(first),
                     "gap": sec["yield"].mean() - first["yield"].mean()})

    keep = ~is_quote(second, INDIANA_S0506_ODD_QUOTE) & ~is_quote(second, INDIANA_S0480_ODD_QUOTE)
    monthly = pd.concat(
        [first.groupby(first.date.dt.to_period("M"))["yield"].mean(),
         second[keep].groupby(second[keep].date.dt.to_period("M"))["yield"].mean()],
        axis=1, join="inner", keys=["paid_first", "paid_second"],
    )
    rows.append({"measure": "Months with both groups quoted, and months paid second yields more "
                            "(group_a = months quoted, group_b = months paid second higher)",
                 "group_a": len(monthly), "n_a": None, "group_b": int((monthly.paid_second > monthly.paid_first).sum()),
                 "n_b": None, "gap": None})

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_DIR / "canal_summary.csv", index=False)
    print("=== Summary numbers (output/canal_summary.csv) ===")
    print(out.round(3).to_string(index=False))
    print()


def print_tranche_summary(indiana: pd.DataFrame) -> None:
    pref = indiana[indiana.tranche == "preferred"]
    defr = indiana[indiana.tranche == "deferred"]
    ov_start = max(pref.date.min(), defr.date.min())
    ov_end = min(pref.date.max(), defr.date.max())
    pref_ov = pref[(pref.date >= ov_start) & (pref.date <= ov_end)]
    defr_ov = defr[(defr.date >= ov_start) & (defr.date <= ov_end)]

    print("=== Indiana preferred vs. deferred tranche test ===")
    print(f"Preferred (S-0490 + S-0500): full-window mean {pref['yield'].mean():.2f}%  n={len(pref)}, "
          f"{pref.date.min().date()} to {pref.date.max().date()}")
    print(f"Deferred  (S-0480 + S-0506): full-window mean {defr['yield'].mean():.2f}%  n={len(defr)}, "
          f"{defr.date.min().date()} to {defr.date.max().date()}")
    print(f"Overlap window ({ov_start.date()} to {ov_end.date()}), apples-to-apples:")
    print(f"  Preferred: mean {pref_ov['yield'].mean():.2f}%  n={len(pref_ov)}")
    print(f"  Deferred:  mean {defr_ov['yield'].mean():.2f}%  n={len(defr_ov)}")
    print(f"  Gap (deferred - preferred): {defr_ov['yield'].mean() - pref_ov['yield'].mean():.2f}pp")
    print()
    print("Raw price levels (not just yield) for a sanity check against a current-yield artifact:")
    for spec in INDIANA_CANAL_SPECS:
        s = indiana[indiana.code == spec["code"]]["price"]
        print(f"  {spec['code']} ({spec['tranche']:>9}, {spec['name']}): "
              f"median price {s.median():.2f}, range {s.min():.1f}-{s.max():.1f}")
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
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    return fig, ax


def build_chart(ny_canal: pd.DataFrame, indiana: pd.DataFrame) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), dpi=150)
    for ax in (ax1, ax2):
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID_COLOR, linewidth=0.8)
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color(AXIS_COLOR)
        ax.tick_params(colors=MUTED_TEXT, labelsize=9)
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.patch.set_facecolor(SURFACE)

    # Left panel: NY canal bonds, usable (non-excluded) rows
    for i, spec in enumerate(NY_CANAL_SPECS):
        s = ny_canal[(ny_canal.code == spec["code"]) & ~ny_canal.excluded_past_maturity & ~ny_canal.excluded_near_maturity]
        s = s[~((s.code == "S-1820") & (s.date == S1820_ANOMALY_DATE))]  # drop the 160.00 anomaly from the line only
        s = s.sort_values("date")
        color_alpha = 0.55 + 0.22 * i
        if spec["code"] == "S-1750":
            # Break the line across the known 1,666-day gap instead of connecting it directly.
            seg1 = s[s.date <= S1750_GAP_START]
            seg2 = s[s.date >= S1750_GAP_END]
            ax1.plot(seg1.date, seg1["yield"], linewidth=1.6, color=NY_COLOR, alpha=color_alpha,
                      label=f"{spec['code']} ({spec['name']})")
            ax1.plot(seg2.date, seg2["yield"], linewidth=1.6, color=NY_COLOR, alpha=color_alpha)
            if len(seg1) and len(seg2):
                ax1.plot([seg1.date.iloc[-1], seg2.date.iloc[0]], [seg1["yield"].iloc[-1], seg2["yield"].iloc[0]],
                          linewidth=1, linestyle=":", color=NY_COLOR, alpha=0.5)
                ax1.annotate("no data\n(1,666-day gap)", xy=(S1750_GAP_START, seg1["yield"].iloc[-1]),
                              xytext=(4, 10), textcoords="offset points", color=NY_COLOR, fontsize=6.5,
                              style="italic", ha="left")
        else:
            ax1.plot(s.date, s["yield"], linewidth=1.6, label=f"{spec['code']} ({spec['name']})", color=NY_COLOR,
                      alpha=color_alpha)
    ax1.axvline(SIGNAL, color=SIGNAL_COLOR, linestyle="--", linewidth=1.2)
    ax1.set_title("New York Canal Bonds (secondary/robustness)", color=PRIMARY_TEXT, fontsize=11, fontweight="bold", loc="left")
    ax1.set_ylabel("Yield (%)", color=PRIMARY_TEXT)
    ax1.legend(fontsize=7, loc="upper right", frameon=False)

    # Right panel: Indiana preferred vs. deferred. One deferred observation (S-0506, 1851-10-08,
    # price $1.00) yields 500% current yield -- real per the formula, but plotting it directly would
    # crush the rest of the series to a flat line near zero. Capped off-chart with an annotation
    # instead of silently excluding or rescaling the whole axis around a single point.
    pref = indiana[indiana.tranche == "preferred"].groupby("date")["yield"].mean().sort_index()
    defr_raw = indiana[indiana.tranche == "deferred"].groupby("date")["yield"].mean().sort_index()
    Y_CAP = 100.0
    n_capped = int((defr_raw > Y_CAP).sum())
    defr = defr_raw.clip(upper=Y_CAP)
    ax2.plot(pref.index, pref.values, color=PREFERRED_COLOR, linewidth=2, label="Preferred (S-0490 + S-0500)")
    ax2.plot(defr.index, defr.values, color=DEFERRED_COLOR, linewidth=2, label="Deferred (S-0480 + S-0506)")
    if n_capped:
        capped_dates = defr_raw[defr_raw > Y_CAP]
        for dt, val in capped_dates.items():
            ax2.annotate(f"{val:.0f}%\n(off-chart)", xy=(dt, Y_CAP), xytext=(0, 6), textcoords="offset points",
                          color=DEFERRED_COLOR, fontsize=7, ha="center", fontweight="bold")
    ax2.set_ylim(0, Y_CAP * 1.08)
    ax2.set_title("Indiana Butler Bill Tranches: Preferred vs. Deferred", color=PRIMARY_TEXT, fontsize=11, fontweight="bold", loc="left")
    ax2.set_ylabel("Current yield (%), capped at 100% -- see note", color=PRIMARY_TEXT, fontsize=9)
    ax2.legend(fontsize=8, loc="upper right", frameon=False)

    fig.suptitle(
        "Canal / Revenue-Pledged Bond Robustness Comparison (secondary series)",
        color=PRIMARY_TEXT, fontsize=14, fontweight="bold", x=0.01, ha="left",
    )

    method_note = (
        "LEFT: New York canal bonds (S-1750, S-1820, S-1950), yield to maturity with the usual near- and "
        "past-maturity exclusions. New York has no default period. Ohio's only canal bond (S-2190) is "
        "dropped: two quotes, both from 1825. RIGHT: Indiana's 1847 Butler Bill canal tranches, current "
        "yield (no maturity date in the codebook). They trade only from 1850, so this panel tests whether "
        "the market priced the preferred/deferred split, not the 1843 signal. All Indiana tranche rows "
        "fall inside Indiana's open-ended default period. S-1750's dotted segment is a 1,666-day gap in "
        "the source data, not interpolation. One S-1820 price (160.00, Oct 1848, probably a transcription "
        "error) is left off the line but kept in the CSV. One deferred-tranche quote (S-0506, Oct 1851, "
        "price $1.00, 500% current yield) is capped at the top of the panel and labeled."
    )
    wrapped_lines = []
    for paragraph in method_note.split("\n"):
        wrapped_lines.extend(textwrap.wrap(paragraph, width=200) or [""])
    wrapped = "\n".join(wrapped_lines)
    fig.text(0.01, 0.01, wrapped, color=SECONDARY_TEXT, fontsize=7.5, ha="left", va="bottom")
    bottom_margin = 0.02 + 0.02 * len(wrapped_lines)
    fig.tight_layout(rect=(0, bottom_margin, 1, 0.94))

    out_path = OUTPUT_DIR / "chart_canal_robustness.png"
    fig.savefig(out_path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"saved -> {out_path}")


def main() -> None:
    ny_df = pd.read_csv(NY_PRICES, index_col=0, parse_dates=True)

    trade_density_report(ny_df)

    ny_canal = build_ny_canal_frame(ny_df)
    indiana = build_indiana_canal_frame(ny_df)

    cols = [
        "date", "state", "code", "name", "tranche", "price", "coupon",
        "yield_measure_used", "yield", "current_yield", "series_label",
        "excluded_near_maturity", "excluded_past_maturity", "active_default_override",
    ]
    out = pd.concat([ny_canal[cols], indiana[cols]], ignore_index=True).sort_values(["state", "code", "date"])
    out_path = OUTPUT_DIR / "canal_robustness_yields.csv"
    out.to_csv(out_path, index=False)
    print(f"saved -> {out_path} ({len(out)} rows)")
    print()

    print_tranche_summary(indiana)
    write_summary(ny_canal, indiana)

    build_chart(ny_canal, indiana)


if __name__ == "__main__":
    main()

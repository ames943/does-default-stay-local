"""Compute bond yields for the primary comparison (Pennsylvania, Ohio, Alabama,
Indiana and New York general-obligation bonds) from the parsed EH.net prices.

Yield measures
--------------
- Yield to maturity, using the standard approximation
      YTM = [C + (F - P) / n] / [(F + P) / 2] * 100
  with C the annual coupon per $100 of face value, F = 100, P the price and n
  the years left to maturity. Used for Pennsylvania, Ohio and New York, whose
  codebook entries give a maturity year.
- Current yield, C / P * 100. Used for Alabama and Indiana. Alabama has no
  maturity in the codebook and Indiana only has "25 years" with no issue date,
  so YTM cannot be computed for either. This makes the measure differ across
  states; the yield_measure_used column records which one each row uses.

The codebook gives only a maturity year, so Jan 1 of that year is used as the
maturity date.

Exclusions (rows are flagged, none are removed from the output)
---------------------------------------------------------------
- excluded_past_maturity: the quote is on or after the bond's stated maturity.
  YTM is undefined without a real redemption date, and no yield is computed.
  Several bonds kept trading past maturity, which says something about the
  issuer in its own right.
- excluded_near_maturity: the quote is within 12 months of maturity. YTM is
  computed but unstable there, because years-to-maturity in the denominator
  goes to zero and small price changes turn into large yield swings.

Active-default override
-----------------------
YTM assumes the bond is redeemed at par on schedule, which is wrong for a state
that is missing payments. For any quote dated inside a state's entry in
DEFAULT_PERIODS, current yield is used instead of YTM, and the near/past
maturity flags are cleared since they only guard the YTM calculation. This was
added after Pennsylvania's S-2410 showed an average YTM near 30% over its whole
usable window against a current yield near 10%.

Alabama is not in DEFAULT_PERIODS. Wallis and other secondary sources say it
raised taxes and liquidated its state bank to keep paying its debt service. It
is on current yield only because its codebook entry has no maturity.
"""

import re
from pathlib import Path
from typing import Optional

import pandas as pd
import xlrd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
CODEBOOK_PATH = RAW_DIR / "Securities Index.xls"

FACE_VALUE = 100.0
NEAR_MATURITY_YEARS = 1.0

STATE_BUCKET = {
    "Pennsylvania": "defaulted",
    "Ohio": "safe",
    # Alabama raised direct taxes in early 1842 and used proceeds from
    # liquidating its state bank to keep paying debt service, so it is not
    # treated as a defaulter. Its use of current yield is a separate matter
    # (no maturity in the codebook).
    "Alabama": "risky_but_survived",
    "Indiana": "defaulted",
    "New York": "risky_but_survived",
}

# No usable maturity date in the codebook (Alabama: blank; Indiana: "25 years"
# with no issue date), so these two always use current yield.
NO_MATURITY_STATES = {"Alabama", "Indiana"}

# Active-default windows as (start, end). end=None means the state is treated as
# still in default through the end of its usable data. The dates come from Wallis
# (2004/2005) and secondary summaries of the 1840s defaults, not from primary
# documents. Alabama is left out on purpose (see above).
DEFAULT_PERIODS = {
    "Pennsylvania": (pd.Timestamp("1842-08-01"), pd.Timestamp("1845-02-01")),
    "Indiana": (pd.Timestamp("1841-01-01"), None),
}

BOND_SPECS = [
    {"code": "S-2240", "state": "Pennsylvania", "source": "pa"},
    {"code": "S-2250", "state": "Pennsylvania", "source": "pa"},
    {"code": "S-2270", "state": "Pennsylvania", "source": "pa"},
    {"code": "S-2330", "state": "Pennsylvania", "source": "pa"},
    {"code": "S-2410", "state": "Pennsylvania", "source": "pa"},
    {"code": "S-2100", "state": "Ohio", "source": "ny_other"},
    {"code": "S-2110", "state": "Ohio", "source": "ny_other"},
    {"code": "S-2080", "state": "Ohio", "source": "ny_other"},
    {"code": "S-2010", "state": "Ohio", "source": "ny_other"},
    {"code": "S-0030", "state": "Alabama", "source": "ny_other"},
    {"code": "S-0040", "state": "Alabama", "source": "ny_other"},
    {"code": "S-0510", "state": "Indiana", "source": "ny_other"},
    {"code": "S-0540", "state": "Indiana", "source": "ny_other"},
    {"code": "S-1650", "state": "New York", "source": "ny_state"},
]


def load_codebook() -> dict:
    """Code -> (name, coupon_pct, maturity_year_or_None)."""
    wb = xlrd.open_workbook(CODEBOOK_PATH)
    sh = wb.sheet_by_name("final")
    out = {}
    for r in range(1, sh.nrows):
        code, name, _type, interest, maturity = sh.row_values(r)
        match = re.match(r"^(\d+(?:\.\d+)?)s?$", str(interest).strip())
        coupon = float(match.group(1)) if match else None
        mat_year = int(maturity) if isinstance(maturity, float) and maturity else None
        out[code] = (name, coupon, mat_year)
    return out


def load_price_series(spec: dict, pa_df: pd.DataFrame, ny_df: pd.DataFrame) -> pd.Series:
    if spec["source"] == "pa":
        return pa_df[spec["code"]].dropna()
    if spec["source"] == "ny_other":
        return ny_df[f"Other State Debt::{spec['code']}"].dropna()
    if spec["source"] == "ny_state":
        return ny_df[f"NY State Debt::{spec['code']}"].dropna()
    raise ValueError(spec["source"])


def compute_ytm(price: pd.Series, coupon: float, n_years: pd.Series) -> pd.Series:
    return (coupon + (FACE_VALUE - price) / n_years) / ((FACE_VALUE + price) / 2) * 100


def in_default_period(state: str, dates: pd.DatetimeIndex) -> pd.Series:
    if state not in DEFAULT_PERIODS:
        return pd.Series(False, index=dates)
    start, end = DEFAULT_PERIODS[state]
    mask = dates >= start
    if end is not None:
        mask &= dates < end
    return pd.Series(mask, index=dates)


def build_bond_frame(spec: dict, price: pd.Series, coupon: float, mat_year: Optional[int]) -> pd.DataFrame:
    state = spec["state"]
    current_yield = coupon / price * 100
    default_override = in_default_period(state, price.index)

    if state in NO_MATURITY_STATES or mat_year is None:
        yield_measure = pd.Series("current_yield", index=price.index)
        yield_value = current_yield
        excluded_near = pd.Series(False, index=price.index)
        excluded_past = pd.Series(False, index=price.index)
    else:
        maturity_date = pd.Timestamp(f"{mat_year}-01-01")
        n_years = (maturity_date - price.index).days / 365.25
        excluded_past = n_years <= 0
        excluded_near = (n_years > 0) & (n_years <= NEAR_MATURITY_YEARS)

        ytm = compute_ytm(price, coupon, n_years)
        yield_value = ytm.where(~excluded_past, other=pd.NA)
        yield_measure = pd.Series("ytm", index=price.index)
        yield_measure = yield_measure.mask(excluded_past, pd.NA)

        # Inside a default period, use current yield and clear the maturity
        # flags (see the module docstring).
        yield_value = yield_value.where(~default_override, current_yield)
        yield_measure = yield_measure.mask(default_override, "current_yield")
        excluded_near = excluded_near & ~default_override
        excluded_past = excluded_past & ~default_override

    return pd.DataFrame(
        {
            "date": price.index,
            "state": state,
            "code": spec["code"],
            "price": price.values,
            "coupon": coupon,
            "yield_measure_used": yield_measure.values,
            "yield": yield_value.values,
            "current_yield": current_yield.values,
            "bucket": STATE_BUCKET[state],
            "series_label": "primary",
            "excluded_near_maturity": pd.Series(excluded_near).values,
            "excluded_past_maturity": pd.Series(excluded_past).values,
            "active_default_override": default_override.values,
        }
    )


def main() -> None:
    codebook = load_codebook()
    pa_df = pd.read_csv(OUTPUT_DIR / "philadelphia_state_debt_prices.csv", index_col=0, parse_dates=True)
    ny_df = pd.read_csv(OUTPUT_DIR / "new_york_state_debt_prices.csv", index_col=0, parse_dates=True)

    frames = []
    print(f"{'code':8} {'state':12} {'coupon':>6} {'maturity':>8} {'total':>6} {'past_mat':>9} {'near_mat':>9} {'usable':>7}  usable_range")
    for spec in BOND_SPECS:
        name, coupon, mat_year = codebook[spec["code"]]
        price = load_price_series(spec, pa_df, ny_df)
        frame = build_bond_frame(spec, price, coupon, mat_year)
        frames.append(frame)

        total = len(frame)
        past = int(frame["excluded_past_maturity"].sum())
        near = int(frame["excluded_near_maturity"].sum())
        usable_mask = ~frame["excluded_past_maturity"] & ~frame["excluded_near_maturity"]
        usable = frame.loc[usable_mask]
        rng = (
            f"{usable['date'].min().date()} to {usable['date'].max().date()}"
            if len(usable)
            else "NONE"
        )
        print(
            f"{spec['code']:8} {spec['state']:12} "
            f"{('n/a' if coupon is None else f'{coupon}%'):>6} "
            f"{(mat_year or 'n/a'):>8} {total:>6} {past:>9} {near:>9} {len(usable):>7}  {rng}"
        )

    out = pd.concat(frames, ignore_index=True).sort_values(["state", "code", "date"])
    out_path = OUTPUT_DIR / "primary_yields.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSaved -> {out_path}  ({len(out)} rows)")


if __name__ == "__main__":
    main()

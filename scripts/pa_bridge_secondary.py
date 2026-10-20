"""Secondary view of Pennsylvania: S-2330 and S-2410 (the primary bonds, through
Dec 1844) followed by S-2460, "Pennsylvania new annual 5s" (through Jan 1847).

S-2460 is not treated as a continuation of the other two. It is a different
named instrument (an undated "annual" loan, against dated fixed-maturity
bonds), which is the same kind of judgment call as the New York S-1650 and
S-1370 splice I rejected. The gap is much smaller here (7 days against 399 for
New York) and the coupons match, but the two segments are kept separate rather
than joined into one line.

Output: output/pa_bridge_secondary.csv, with a `segment` column marking which
instrument group each row belongs to.
"""

from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def main() -> None:
    primary = pd.read_csv(OUTPUT_DIR / "primary_yields.csv", parse_dates=["date"])
    pa_primary = primary[
        (primary.state == "Pennsylvania")
        & primary.code.isin(["S-2330", "S-2410"])
        & ~primary.excluded_past_maturity
        & ~primary.excluded_near_maturity
    ].copy()
    pa_primary["segment"] = "S-2330/S-2410 (fixed-maturity, primary series)"

    pa_df = pd.read_csv(OUTPUT_DIR / "philadelphia_state_debt_prices.csv", index_col=0, parse_dates=True)
    bridge_price = pa_df["S-2460"].dropna().sort_index()
    bridge = pd.DataFrame(
        {
            "date": bridge_price.index,
            "state": "Pennsylvania",
            "code": "S-2460",
            "price": bridge_price.values,
            "coupon": 5.0,
            "yield_measure_used": "current_yield",
            "yield": 5.0 / bridge_price.values * 100,
            "current_yield": 5.0 / bridge_price.values * 100,
            "bucket": "defaulted",
            "series_label": "secondary_pa_bridge",
            "excluded_near_maturity": False,
            "excluded_past_maturity": False,
            "segment": 'S-2460 "new annual 5s" (different named instrument, not a splice)',
        }
    )

    pa_primary["series_label"] = "secondary_pa_bridge"
    out = pd.concat([pa_primary, bridge], ignore_index=True).sort_values("date")

    s2330_last = pa_primary.loc[pa_primary.code == "S-2330", "date"].max()
    s2410_last = pa_primary.loc[pa_primary.code == "S-2410", "date"].max()
    first_bridge = bridge["date"].min()
    print(f"S-2330 last obs: {s2330_last.date()}  ->  S-2460 first obs: {first_bridge.date()}  "
          f"(gap {(first_bridge - s2330_last).days} days)")
    print(f"S-2410 last obs: {s2410_last.date()}  ->  S-2460 first obs: {first_bridge.date()}  "
          f"(S-2410 and S-2460 overlap by {(s2410_last - first_bridge).days} days -- "
          f"corroborates they are distinct, independently-traded instruments, not a continuation)")

    out_path = OUTPUT_DIR / "pa_bridge_secondary.csv"
    out.to_csv(out_path, index=False)
    print(f"Saved -> {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()

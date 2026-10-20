"""Newey-West (HAC) standard errors for the city/state yield gaps.

For each pair, the gap is the state's mean yield minus the city's mean yield on
dates when both are quoted (inner join on date). The standard error is
Newey-West with a Bartlett kernel and lag L = floor(4 * (n / 100) ** (2 / 9)),
since the weekly quotes are strongly autocorrelated.

Windows
-------
- Philadelphia, before the signal: all matched dates before Feb 11 1843 (SIGNAL_DATE).
  Dates from Feb 11 to Mar 31 1843 are in neither window.
- Philadelphia, after: Feb 3 1844 to Jan 25 1845, the dates where C-1100 and
  Pennsylvania are both quoted after C-1100's gap.
- Pittsburgh, after: Apr 1 1843 (AFTER_START) to Jan 25 1845, Pennsylvania's coverage ceiling.
- Cincinnati, after: Apr 1 1843 onward.
The change for Philadelphia is after minus before, with the two standard errors
combined as independent.

Output: output/hac_standard_errors.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

SIGNAL_DATE = pd.Timestamp("1843-02-11")  # no-bailout signal; ends the before window
AFTER_START = pd.Timestamp("1843-04-01")  # start of the after-signal windows
PA_CEILING = pd.Timestamp("1845-01-25")
PHILADELPHIA_POST_START = pd.Timestamp("1844-02-03")


def newey_west(x: np.ndarray) -> tuple:
    n = len(x)
    lag = int(np.floor(4 * (n / 100) ** (2 / 9)))
    u = x - x.mean()
    var = u @ u / n
    for k in range(1, lag + 1):
        var += 2 * (1 - k / (lag + 1)) * (u[k:] @ u[:-k]) / n
    return x.mean(), np.sqrt(var / n), lag


def matched_gap(csv_name: str, start: pd.Timestamp, end: pd.Timestamp) -> np.ndarray:
    df = pd.read_csv(OUTPUT_DIR / csv_name, parse_dates=["date"])
    state = df[df.level == "state"].groupby("date")["yield"].mean()
    city = df[df.level == "city"].groupby("date")["yield"].mean()
    both = pd.concat([state, city], axis=1, join="inner", keys=["state", "city"])
    both = both[(both.index >= start) & (both.index <= end)]
    return (both["state"] - both["city"]).to_numpy()


def main() -> None:
    windows = [
        ("Philadelphia/PA, before signal", "city_vs_state_yields.csv", pd.Timestamp("1800-01-01"), SIGNAL_DATE - pd.Timedelta(days=1)),
        ("Philadelphia/PA, after signal", "city_vs_state_yields.csv", PHILADELPHIA_POST_START, PA_CEILING),
        ("Pittsburgh/PA, after signal", "city_vs_state_pittsburgh.csv", AFTER_START, PA_CEILING),
        ("Cincinnati/Ohio, after signal", "city_vs_state_cincinnati.csv", AFTER_START, pd.Timestamp("2000-01-01")),
    ]
    rows = []
    for label, csv_name, start, end in windows:
        n_dates = len(gap := matched_gap(csv_name, start, end))
        mean, se, lag = newey_west(gap)
        rows.append({"window": label, "n": n_dates, "lag": lag, "mean_gap_pp": mean, "hac_se": se,
                     "ci_low": mean - 1.96 * se, "ci_high": mean + 1.96 * se})

    pre, post = rows[0], rows[1]
    change = post["mean_gap_pp"] - pre["mean_gap_pp"]
    change_se = np.hypot(pre["hac_se"], post["hac_se"])
    rows.append({"window": "Philadelphia/PA, change (after - before)", "n": None, "lag": None,
                 "mean_gap_pp": change, "hac_se": change_se,
                 "ci_low": change - 1.96 * change_se, "ci_high": change + 1.96 * change_se})

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_DIR / "hac_standard_errors.csv", index=False)
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()

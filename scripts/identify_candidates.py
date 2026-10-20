"""Narrow down which S- codes might correspond to which states, by behavior
pattern, cross-checked against the Securities Index.xls codebook.

It flags:
  - default-risk-shaped price drops (>25% within a 6-month window, 1837-1845)
  - Philadelphia columns matching PA's known ~80s -> 50s/60s decline into its
    August 1842 default
  - New York columns (true "NY State Debt" sheet only -- New-York.xls also
    has an "Other State Debt" sheet with non-NY bonds) that stayed flat or
    recovered quickly over the same window, as candidates for bonds that
    avoided default

Each output row is enriched with the confirmed security name from
Securities Index.xls where available.

Output: output/candidate_state_codes.csv
"""

from pathlib import Path

import xlrd
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

SOURCE_FILES = {
    "New-York.xls": OUTPUT_DIR / "new_york_state_debt_prices.csv",
    "Philadelphia1.xls": OUTPUT_DIR / "philadelphia_state_debt_prices.csv",
}

CODEBOOK_PATH = RAW_DIR / "Securities Index.xls"

# Manual notes for codes already confirmed to be mislabeled by the "New York
# candidates" heuristic below -- these live in New-York.xls's "Other State
# Debt" sheet, not "NY State Debt", so they are not New York bonds.
KNOWN_BUCKET_NOTES = {
    "S-2100": "Ohio -- safe candidate (never defaulted), not NY",
    "S-2110": "Ohio -- safe candidate (never defaulted), not NY",
    "S-2080": "Ohio -- safe candidate (never defaulted), not NY",
    "S-2010": "Ohio -- safe candidate (never defaulted), not NY",
    "S-0030": "Alabama -- likely defaulted candidate, not NY",
    "S-0040": "Alabama -- likely defaulted candidate, not NY",
    "S-0510": "Indiana -- likely defaulted candidate (1846 Butler Bill), not NY",
    "S-0540": "Indiana -- likely defaulted candidate (1846 Butler Bill), not NY",
}


def load_codebook() -> dict:
    """Code -> confirmed security name, from Securities Index.xls."""
    if not CODEBOOK_PATH.exists():
        return {}
    wb = xlrd.open_workbook(CODEBOOK_PATH)
    sh = wb.sheet_by_name("final")
    return {row[0]: row[1] for row in (sh.row_values(r) for r in range(1, sh.nrows))}


def bare_code(col: str) -> str:
    """Strip a 'NY State Debt::' / 'Other State Debt::' sheet-source prefix."""
    return col.split("::", 1)[-1]

CRISIS_START = pd.Timestamp("1837-01-01")
CRISIS_END = pd.Timestamp("1845-12-31")
DROP_WINDOW = pd.Timedelta(days=183)  # ~6 months
DROP_THRESHOLD = 0.25
RECOVERY_WINDOW = pd.Timedelta(days=548)  # ~18 months
RECOVERY_FRACTION = 0.90

PA_DECLINE_PEAK_RANGE = (75, 95)
PA_DECLINE_TROUGH_RANGE = (40, 66)


def load_series(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df.sort_index()


def column_summary(s: pd.Series, full_index: pd.DatetimeIndex) -> dict:
    s = s.dropna()
    n_possible = len(full_index)
    n_present = len(s)
    return {
        "date_start": s.index.min() if n_present else pd.NaT,
        "date_end": s.index.max() if n_present else pd.NaT,
        "pct_populated": 100 * n_present / n_possible if n_possible else 0.0,
        "avg_price": s.mean() if n_present else float("nan"),
        "volatility": s.std() if n_present > 1 else float("nan"),
        "n_present": n_present,
    }


def find_drops(s: pd.Series):
    """Find (peak_date, peak_price, trough_date, trough_price, pct_drop)
    events where price falls > DROP_THRESHOLD within DROP_WINDOW, with the
    trough or peak falling inside the 1837-1845 crisis window."""
    s = s.dropna().sort_index()
    events = []
    dates = s.index.to_numpy()
    values = s.to_numpy()

    for i in range(len(s)):
        trough_date = s.index[i]
        trough_price = values[i]
        window_start = trough_date - DROP_WINDOW
        mask = (s.index >= window_start) & (s.index <= trough_date)
        window = s[mask]
        if window.empty:
            continue
        peak_price = window.max()
        peak_date = window.idxmax()
        if peak_price <= 0 or peak_date == trough_date:
            continue
        pct_drop = (peak_price - trough_price) / peak_price
        if pct_drop > DROP_THRESHOLD:
            in_crisis = (CRISIS_START <= trough_date <= CRISIS_END) or (
                CRISIS_START <= peak_date <= CRISIS_END
            )
            if in_crisis:
                events.append((peak_date, peak_price, trough_date, trough_price, pct_drop))

    # de-duplicate overlapping events, keep the deepest drop per local cluster
    events.sort(key=lambda e: e[2])  # by trough_date
    deduped = []
    for ev in events:
        if deduped and (ev[2] - deduped[-1][2]) <= DROP_WINDOW:
            if ev[4] > deduped[-1][4]:
                deduped[-1] = ev
        else:
            deduped.append(ev)
    return deduped


def recovers_quickly(s: pd.Series, trough_date, peak_price) -> bool:
    s = s.dropna().sort_index()
    window = s[(s.index > trough_date) & (s.index <= trough_date + RECOVERY_WINDOW)]
    if window.empty:
        return False
    return window.max() >= RECOVERY_FRACTION * peak_price


def main():
    all_rows = []
    codebook = load_codebook()

    for source_file, csv_path in SOURCE_FILES.items():
        if not csv_path.exists():
            print(f"missing {csv_path}, run scripts/parse_securities.py first")
            continue

        df = load_series(csv_path)
        print(f"\n{'=' * 70}\n{source_file}: {df.shape[1]} securities\n{'=' * 70}")

        summaries = {}
        drop_events = {}
        for col in df.columns:
            summaries[col] = column_summary(df[col], df.index)
            drop_events[col] = find_drops(df[col])

        # --- 1. summary table sorted by % populated ---
        summary_df = pd.DataFrame(summaries).T
        summary_df = summary_df.sort_values("pct_populated", ascending=False)
        print("\n-- Column summary (sorted by %% populated) --")
        with pd.option_context("display.max_rows", None, "display.width", 140):
            print(
                summary_df[
                    ["date_start", "date_end", "pct_populated", "avg_price", "volatility"]
                ].round(2)
            )

        # --- 2. flagged sharp drops, 1837-1845 ---
        print("\n-- Flagged sharp declines (>25% within 6 months), 1837-1845 --")
        for col, events in drop_events.items():
            if not events:
                continue
            for peak_date, peak_price, trough_date, trough_price, pct_drop in events:
                print(
                    f"  {col}: {peak_date.date()} @ {peak_price:.2f} -> "
                    f"{trough_date.date()} @ {trough_price:.2f} "
                    f"({pct_drop:.0%} drop)"
                )

        # --- 3. Philadelphia: PA-shaped decline, full 1835-1845 history ---
        if source_file == "Philadelphia1.xls":
            print("\n-- Candidates matching PA's ~80s -> 50s/60s decline into Aug 1842 default --")
            pa_like_cols = []
            for col, events in drop_events.items():
                for peak_date, peak_price, trough_date, trough_price, pct_drop in events:
                    if (
                        PA_DECLINE_PEAK_RANGE[0] <= peak_price <= PA_DECLINE_PEAK_RANGE[1]
                        and PA_DECLINE_TROUGH_RANGE[0] <= trough_price <= PA_DECLINE_TROUGH_RANGE[1]
                        and pd.Timestamp("1841-01-01") <= peak_date <= pd.Timestamp("1842-12-31")
                    ):
                        pa_like_cols.append(col)
                        break
            pa_like_cols = sorted(set(pa_like_cols))
            print(f"  matches: {pa_like_cols}")
            for col in pa_like_cols:
                s = df[col].dropna()
                window = s[(s.index >= "1835-01-01") & (s.index <= "1845-12-31")]
                print(f"\n  {col} full history 1835-1845:")
                for d, v in window.items():
                    print(f"    {d.date()}  {v:.2f}")

        # --- 4. New York: flat / quick-recovery candidates ---
        # Restricted to the real "NY State Debt" sheet only -- New-York.xls
        # also contains an "Other State Debt" sheet (Ohio, Alabama, Indiana,
        # etc. bonds quoted on the NY market), which are not New York bonds
        # and must not be mistaken for "survived" NY candidates.
        if source_file == "New-York.xls":
            print("\n-- Candidates that stayed flat or recovered quickly (1837-1845), true NY State Debt sheet only --")
            ny_cols = [c for c in df.columns if c.startswith("NY State Debt::")]
            ny_candidates = []
            for col in ny_cols:
                s = df[col].dropna()
                window = s[(s.index >= CRISIS_START) & (s.index <= CRISIS_END)]
                if len(window) < 3:
                    continue  # not enough data in the window to judge
                events = drop_events[col]
                if not events:
                    ny_candidates.append((col, "flat", None))
                else:
                    deepest = max(events, key=lambda e: e[4])
                    if recovers_quickly(df[col], deepest[2], deepest[1]):
                        ny_candidates.append((col, "recovered_quickly", deepest[4]))
            for col, kind, pct_drop in ny_candidates:
                extra = f" (recovered after {pct_drop:.0%} drop)" if pct_drop else ""
                print(f"  {col}: {kind}{extra}")

        # --- accumulate rows for final CSV ---
        for col in df.columns:
            summ = summaries[col]
            code = bare_code(col)
            all_rows.append(
                {
                    "code": col,
                    "source_file": source_file,
                    "confirmed_name": codebook.get(code, ""),
                    "bucket_note": KNOWN_BUCKET_NOTES.get(code, ""),
                    "avg_price": round(summ["avg_price"], 2) if pd.notna(summ["avg_price"]) else "",
                    "volatility": round(summ["volatility"], 2) if pd.notna(summ["volatility"]) else "",
                    "pct_populated": round(summ["pct_populated"], 2),
                    "flagged_decline": "yes" if drop_events[col] else "no",
                }
            )

    out_path = OUTPUT_DIR / "candidate_state_codes.csv"
    pd.DataFrame(all_rows).to_csv(out_path, index=False)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()

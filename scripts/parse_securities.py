"""Parse raw EH.net securities price files into clean per-file CSVs.

Extracts state debt ("S-" prefixed) security price series, indexed by date.
Does not attempt to map security codes to specific states -- that is a
separate downstream step.

Files differ in layout:
  - Philadelphia1.xls has a single combined "U.S. and State Debt" sheet.
  - New-York.xls splits the same kind of data across "NY State Debt" and
    "Other State Debt" sheets (plus a separate "U.S. Debt" sheet we don't
    need here); all three share an identical date index, so the state debt
    sheets are concatenated column-wise.
"""

import re
from pathlib import Path

import pandas as pd
import xlrd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

FILES = {
    "New-York.xls": "new_york_state_debt_prices.csv",
    "Philadelphia1.xls": "philadelphia_state_debt_prices.csv",
}


def excel_year_monthday_to_datetime(series: pd.Series) -> pd.Series:
    """Convert a 'year.monthday' float (e.g. 1841.0807) to a datetime.

    Integer part is the year; the fractional part, read as a 4-digit
    zero-padded number, is month (2 digits) + day (2 digits).
    """
    as_str = series.astype(float).map(lambda v: f"{v:.4f}")
    year = as_str.str.slice(0, 4)
    month_day = as_str.str.split(".").str[1].str.ljust(4, "0")
    month = month_day.str.slice(0, 2)
    day = month_day.str.slice(2, 4)
    date_str = year + month + day
    return pd.to_datetime(date_str, format="%Y%m%d", errors="coerce")


def is_state_debt_column(name: str) -> bool:
    return bool(re.match(r"^S-\d+$", str(name).strip()))


def sheet_to_frame(wb: xlrd.Book, sheet_name: str) -> pd.DataFrame:
    sh = wb.sheet_by_name(sheet_name)
    header = sh.row_values(0)
    rows = [sh.row_values(r) for r in range(1, sh.nrows)]
    df = pd.DataFrame(rows, columns=header)
    return df


def find_state_debt_sheets(wb: xlrd.Book) -> list[str]:
    names = wb.sheet_names()
    if "U.S. and State Debt" in names:
        return ["U.S. and State Debt"]
    return [n for n in names if "state debt" in n.lower() and not n.lower().startswith("u.s")]


def parse_file(xls_path: Path) -> pd.DataFrame:
    wb = xlrd.open_workbook(xls_path)
    sheet_names = find_state_debt_sheets(wb)

    # When a file splits state debt across multiple sheets (e.g. New-York.xls
    # has "NY State Debt" and "Other State Debt"), a bare "S-" code is
    # ambiguous -- the same code can denote different securities in different
    # sheets/files. Tag each column with its source sheet before concatenating
    # so downstream scripts can filter to a specific sheet's real columns.
    tag_columns = len(sheet_names) > 1

    frames = []
    date_col = None
    for sheet_name in sheet_names:
        df = sheet_to_frame(wb, sheet_name)
        first_col = df.columns[0]
        if date_col is None:
            date_col = df[first_col]
        state_cols = [c for c in df.columns if is_state_debt_column(c)]
        sheet_df = df[state_cols]
        if tag_columns:
            sheet_df = sheet_df.rename(columns={c: f"{sheet_name}::{c}" for c in state_cols})
        frames.append(sheet_df)

    combined = pd.concat(frames, axis=1)
    combined.insert(0, "date", excel_year_monthday_to_datetime(date_col))
    combined = combined.dropna(subset=["date"]).set_index("date").sort_index()

    # replace blank strings with NaN, coerce prices to numeric
    combined = combined.replace("", pd.NA)
    combined = combined.apply(pd.to_numeric, errors="coerce")

    return combined


def summarize(name: str, df: pd.DataFrame) -> None:
    n_securities = df.shape[1]
    date_min, date_max = df.index.min(), df.index.max()
    total_cells = df.shape[0] * df.shape[1]
    non_empty = df.notna().sum().sum()
    pct_full = 100 * non_empty / total_cells if total_cells else 0.0

    print(f"--- {name} ---")
    print(f"  securities (S- codes): {n_securities}")
    print(f"  date range: {date_min.date()} to {date_max.date()}")
    print(f"  rows (dates): {df.shape[0]}")
    print(f"  non-empty cells: {non_empty} / {total_cells} ({pct_full:.2f}% populated)")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for raw_name, out_name in FILES.items():
        raw_path = RAW_DIR / raw_name
        if not raw_path.exists():
            print(f"skipping {raw_name}: not found in {RAW_DIR}")
            continue

        df = parse_file(raw_path)
        out_path = OUTPUT_DIR / out_name
        df.to_csv(out_path)

        summarize(raw_name, df)
        print(f"  saved -> {out_path}")
        print()


if __name__ == "__main__":
    main()

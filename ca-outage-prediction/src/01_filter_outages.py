"""Step 1: read the raw EAGLE-I yearly files and keep only our CA counties.

Input : data/raw/eaglei/eaglei_outages_*.csv  (download instructions in README)
Output: data/interim/outages_15min.csv

The raw files are hundreds of MB each, so we read them in chunks and keep
only the four columns we need.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import EAGLEI_DIR, FIPS_TO_COUNTY, HANDOFF_EAGLEI_DIR, INTERIM_DIR  # noqa: E402

CHUNK_SIZE = 1_000_000
OUT_PATH = INTERIM_DIR / "outages_15min.csv"

# Raw yearly files live in either place; .gz is read transparently by pandas.
SEARCH_DIRS = [EAGLEI_DIR, HANDOFF_EAGLEI_DIR]
RAW_PATTERN = "eaglei_outages_*.csv*"
# An already-filtered file handed over by someone who ran this step elsewhere.
PREFILTERED_PATTERN = "outages_15min.csv*"

# EAGLE-I has shipped the customer count under both names over the years.
COLUMN_ALIASES = {"sum": "customers_out", "customers_out": "customers_out"}


def normalise(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk = chunk.rename(columns={c: c.strip().lower() for c in chunk.columns})
    count_col = next((c for c in COLUMN_ALIASES if c in chunk.columns), None)
    if count_col is None:
        raise ValueError(f"no customer-count column found in {list(chunk.columns)}")
    chunk = chunk.rename(columns={count_col: "customers_out"})
    return chunk[["fips_code", "run_start_time", "customers_out"]]


def find(pattern: str) -> list[Path]:
    return sorted(p for d in SEARCH_DIRS if d.exists() for p in d.glob(pattern))


def adopt_prefiltered(path: Path) -> None:
    """Someone already ran this step; just validate and copy into place."""
    print(f"using pre-filtered {path}")
    df = pd.read_csv(path)
    required = {"fips_code", "run_start_time", "customers_out"}
    if not required.issubset(df.columns):
        raise SystemExit(f"{path} is missing columns: {sorted(required - set(df.columns))}")
    df["county"] = df["fips_code"].map(FIPS_TO_COUNTY)
    unknown = df["county"].isna().sum()
    if unknown:
        print(f"dropping {unknown:,} rows from counties not in config.py")
        df = df.dropna(subset=["county"])
    df.to_csv(OUT_PATH, index=False)
    print(f"wrote {len(df):,} rows for {df['county'].nunique()} counties -> {OUT_PATH}")


def main() -> None:
    prefiltered = find(PREFILTERED_PATTERN)
    if prefiltered:
        adopt_prefiltered(prefiltered[0])
        return

    files = find(RAW_PATTERN)
    if not files:
        searched = " or ".join(str(d) for d in SEARCH_DIRS)
        raise SystemExit(
            f"No EAGLE-I files in {searched}. See the README for the download link."
        )

    keep_fips = set(FIPS_TO_COUNTY)
    kept = []

    for path in files:
        rows_in = rows_out = 0
        for chunk in pd.read_csv(path, chunksize=CHUNK_SIZE, low_memory=False):
            rows_in += len(chunk)
            chunk = normalise(chunk)
            chunk = chunk[chunk["fips_code"].isin(keep_fips)]
            if not chunk.empty:
                rows_out += len(chunk)
                kept.append(chunk)
        print(f"{path.name}: {rows_in:,} rows read, {rows_out:,} kept")

    if not kept:
        raise SystemExit("None of the configured counties appear in the raw files.")

    df = pd.concat(kept, ignore_index=True)
    df["county"] = df["fips_code"].map(FIPS_TO_COUNTY)
    df["run_start_time"] = pd.to_datetime(df["run_start_time"], errors="coerce")
    df["customers_out"] = pd.to_numeric(df["customers_out"], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["run_start_time", "customers_out"])
    if before != len(df):
        print(f"dropped {before - len(df):,} rows with an unparseable time or count")

    df = df.sort_values(["county", "run_start_time"])
    df.to_csv(OUT_PATH, index=False)
    print(f"\nwrote {len(df):,} rows for {df['county'].nunique()} counties -> {OUT_PATH}")


if __name__ == "__main__":
    main()

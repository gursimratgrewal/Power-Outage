"""Step 2: collapse the 15-minute outage records into one row per county-day.

Input : data/interim/outages_15min.csv
Output: data/interim/outages_daily.csv

Two daily measures:
  peak_customers_out  -- the worst 15-minute reading of the day (our target)
  customer_hours_out  -- sum of readings x 0.25h, i.e. total disruption

EAGLE-I only stores intervals where customers were out, so a county-day with
no rows is a quiet day. We reindex to a complete calendar and fill those
with zero -- see the limitations section of the README.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import COUNTIES, END_DATE, INTERIM_DIR, START_DATE  # noqa: E402

IN_PATH = INTERIM_DIR / "outages_15min.csv"
OUT_PATH = INTERIM_DIR / "outages_daily.csv"

INTERVAL_HOURS = 0.25


def main() -> None:
    if not IN_PATH.exists():
        raise SystemExit(f"{IN_PATH} not found -- run 01_filter_outages.py first.")

    df = pd.read_csv(IN_PATH, parse_dates=["run_start_time"])
    df["date"] = df["run_start_time"].dt.normalize()

    daily = (
        df.groupby(["county", "date"])["customers_out"]
        .agg(peak_customers_out="max", _sum="sum")
        .reset_index()
    )
    daily["customer_hours_out"] = daily.pop("_sum") * INTERVAL_HOURS

    # Complete county x date grid so quiet days exist as explicit zeros.
    counties = [c["county"] for c in COUNTIES]
    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    grid = pd.MultiIndex.from_product([counties, dates], names=["county", "date"])

    daily = (
        daily.set_index(["county", "date"])
        .reindex(grid)
        .fillna({"peak_customers_out": 0.0, "customer_hours_out": 0.0})
        .reset_index()
    )

    daily.to_csv(OUT_PATH, index=False)
    print(f"wrote {len(daily):,} county-days -> {OUT_PATH}")
    print(
        daily.groupby("county")["peak_customers_out"]
        .describe()[["mean", "50%", "max"]]
        .round(0)
    )


if __name__ == "__main__":
    main()

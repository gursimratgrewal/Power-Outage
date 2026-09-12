"""Step 4: join outages to weather, engineer features, define the target.

Inputs : data/interim/outages_daily.csv, data/interim/weather_daily.csv
Output : data/processed/model_table.csv

Every feature here is built only from weather, which a forecast gives you a
day ahead. Nothing is derived from past outage counts, so the model can be
run on tomorrow's forecast without waiting for tomorrow's outage data.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import (  # noqa: E402
    FEATURES,
    HIGH_OUTAGE_QUANTILE,
    INTERIM_DIR,
    OUTPUT_DIR,
    PROCESSED_DIR,
    TEST_START,
    TRAIN_END,
)

OUTAGE_PATH = INTERIM_DIR / "outages_daily.csv"
WEATHER_PATH = INTERIM_DIR / "weather_daily.csv"
OUT_PATH = PROCESSED_DIR / "model_table.csv"

RAIN_MM = 1.0  # a "rainy day" -- below this is drizzle


def add_features(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("date").copy()

    group["gust_max_lag1"] = group["gust_max"].shift(1)
    group["precip_lag1"] = group["precip"].shift(1)

    group["gust_3d_mean"] = group["gust_max"].rolling(3, min_periods=1).mean()
    group["gust_7d_mean"] = group["gust_max"].rolling(7, min_periods=1).mean()
    group["precip_3d_sum"] = group["precip"].rolling(3, min_periods=1).sum()
    group["precip_7d_sum"] = group["precip"].rolling(7, min_periods=1).sum()
    group["temp_7d_mean"] = group["temp_mean"].rolling(7, min_periods=1).mean()

    # Days since the last day with meaningful rain. Counts up during a dry
    # spell and resets to 0 on a rainy day -- dry fuel plus wind is the
    # combination utilities worry about.
    rained = group["precip"].fillna(0) >= RAIN_MM
    since = np.empty(len(group), dtype=float)
    counter = np.nan
    for i, wet in enumerate(rained.to_numpy()):
        counter = 0.0 if wet else (counter + 1.0 if not np.isnan(counter) else np.nan)
        since[i] = counter
    group["days_since_rain"] = since

    return group


def main() -> None:
    for path in (OUTAGE_PATH, WEATHER_PATH):
        if not path.exists():
            raise SystemExit(f"{path} not found -- run the earlier steps first.")

    outages = pd.read_csv(OUTAGE_PATH, parse_dates=["date"])
    weather = pd.read_csv(WEATHER_PATH, parse_dates=["date"]).rename(
        columns={
            "wind_gusts_10m_max": "gust_max",
            "wind_speed_10m_max": "wind_max",
            "temperature_2m_mean": "temp_mean",
            "temperature_2m_max": "temp_max",
            "precipitation_sum": "precip",
        }
    )

    df = outages.merge(weather, on=["county", "date"], how="inner")
    print(f"joined {len(df):,} county-days ({df['county'].nunique()} counties)")

    df = pd.concat(
        [add_features(group) for _, group in df.groupby("county")], ignore_index=True
    )

    df["month"] = df["date"].dt.month
    df["day_of_week"] = df["date"].dt.dayofweek

    # Time-based split: train on the early years, test on the late ones.
    df["split"] = pd.NA
    df.loc[df["date"] <= pd.Timestamp(TRAIN_END), "split"] = "train"
    df.loc[df["date"] >= pd.Timestamp(TEST_START), "split"] = "test"
    df = df.dropna(subset=["split"])

    # Target: top 5% of peak customers out *for that county*, with the
    # threshold taken from the training years only. Using all years would let
    # the test period's own extremes set the bar it is judged against.
    train = df[df["split"] == "train"]
    thresholds = train.groupby("county")["peak_customers_out"].quantile(
        HIGH_OUTAGE_QUANTILE
    )
    df["threshold"] = df["county"].map(thresholds)
    df["high_outage_day"] = (
        (df["peak_customers_out"] > df["threshold"]) & (df["peak_customers_out"] > 0)
    ).astype(int)

    before = len(df)
    df = df.dropna(subset=FEATURES)
    print(f"dropped {before - len(df):,} rows with missing features (window warm-up)")

    df.to_csv(OUT_PATH, index=False)

    summary = (
        df.groupby(["county", "split"])["high_outage_day"]
        .agg(days="size", high_days="sum")
        .reset_index()
    )
    summary["rate"] = (summary["high_days"] / summary["days"]).round(3)
    summary.to_csv(OUTPUT_DIR / "target_summary.csv", index=False)

    print(f"\nwrote {len(df):,} rows x {len(FEATURES)} features -> {OUT_PATH}")
    print("\nhigh-outage-day rate by split:")
    print(df.groupby("split")["high_outage_day"].agg(["size", "sum", "mean"]).round(4))


if __name__ == "__main__":
    main()

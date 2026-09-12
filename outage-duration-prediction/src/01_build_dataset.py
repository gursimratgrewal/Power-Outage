"""Step 1: clean the OE-417 events, engineer features, define the target.

Input : data/grid_disruption_2000_2014.csv.gz
Output: data/processed/events.csv

Every feature here is knowable the moment an event is first reported: what
caused it, where, when, and how busy the grid has been lately. Nothing
describes how the event turned out.

Two columns are deliberately left out -- see the README. "Number of
Customers Affected" and "Demand Loss (MW)" are the *final* reported figures,
filed after restoration, so a model using them to predict restoration time
would be reading the answer.
"""

import re
import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import (  # noqa: E402
    CAUSE_PATTERNS,
    DATASET_PATH,
    LONG_HOURS,
    MAX_PLAUSIBLE_HOURS,
    OTHER_CAUSE,
    OUTPUT_DIR,
    SOURCE_PATH,
    TEST_START_YEAR,
    TRAIN_END_YEAR,
)


def label_cause(descriptions: pd.Series) -> pd.Series:
    """First matching pattern wins, most specific first."""
    text = descriptions.fillna("").str.lower()
    cause = pd.Series(OTHER_CAUSE, index=descriptions.index)
    assigned = pd.Series(False, index=descriptions.index)
    for label, pattern in CAUSE_PATTERNS:
        hit = text.str.contains(pattern, regex=True) & ~assigned
        cause[hit] = label
        assigned |= hit
    return cause


def count_areas(areas: pd.Series) -> pd.Series:
    """Rough breadth of an event: how many places its description names."""
    return (
        areas.fillna("")
        .str.split(r"[,;&]|\band\b", regex=True)
        .apply(lambda parts: max(1, len([p for p in parts if p.strip()])))
    )


def rolling_counts(df: pd.DataFrame) -> pd.DataFrame:
    """How busy the grid has been lately, counting only *earlier* events.

    A time-indexed rolling count with closed="left" excludes the current row,
    so an event never counts itself and never sees anything after it.
    """
    df = df.sort_values("began").copy()

    national = (
        df.set_index("began")
        .assign(one=1)["one"]
        .rolling("30D", closed="left")
        .count()
    )
    df["events_national_30d"] = national.to_numpy()

    for window, column in (("7D", "events_region_7d"), ("30D", "events_region_30d")):
        counts = []
        for _, group in df.groupby("nerc_region", sort=False):
            series = (
                group.set_index("began")
                .assign(one=1)["one"]
                .rolling(window, closed="left")
                .count()
            )
            counts.append(pd.Series(series.to_numpy(), index=group.index))
        df[column] = pd.concat(counts).reindex(df.index)

    return df.fillna({"events_national_30d": 0, "events_region_7d": 0, "events_region_30d": 0})


def main() -> None:
    if not SOURCE_PATH.exists():
        raise SystemExit(f"{SOURCE_PATH} not found.")

    raw = pd.read_csv(SOURCE_PATH)
    print(f"read {len(raw):,} reported events, {raw.Year.min()}-{raw.Year.max()}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # mixed date formats, handled by coerce
        began = pd.to_datetime(
            raw["Date Event Began"] + " " + raw["Time Event Began"], errors="coerce"
        )
        restored = pd.to_datetime(
            raw["Date of Restoration"] + " " + raw["Time of Restoration"], errors="coerce"
        )

    df = pd.DataFrame({"began": began, "restored": restored})
    df["duration_hours"] = (df["restored"] - df["began"]).dt.total_seconds() / 3600

    unparsed = df["duration_hours"].isna().sum()
    implausible = (~df["duration_hours"].between(0, MAX_PLAUSIBLE_HOURS)).sum() - unparsed
    df = df[df["duration_hours"].between(0, MAX_PLAUSIBLE_HOURS)].copy()
    print(f"dropped {unparsed:,} events with no restoration time recorded")
    print(f"dropped {implausible:,} with a negative or >30-day duration (data entry errors)")

    keep = df.index
    df["cause"] = label_cause(raw.loc[keep, "Event Description"])
    df["nerc_region"] = raw.loc[keep, "NERC Region"].fillna("Unknown").str.strip()
    df["n_areas"] = count_areas(raw.loc[keep, "Geographic Areas"])
    df["geographic_areas"] = raw.loc[keep, "Geographic Areas"]
    df["description"] = raw.loc[keep, "Event Description"]

    df["month"] = df["began"].dt.month
    df["hour_began"] = df["began"].dt.hour
    df["day_of_week"] = df["began"].dt.dayofweek
    df["year"] = df["began"].dt.year

    df = rolling_counts(df)

    df["long_event"] = (df["duration_hours"] > LONG_HOURS).astype(int)
    df["split"] = pd.NA
    df.loc[df["year"] <= TRAIN_END_YEAR, "split"] = "train"
    df.loc[df["year"] >= TEST_START_YEAR, "split"] = "test"
    df = df.dropna(subset=["split"])

    df.to_csv(DATASET_PATH, index=False)

    by_cause = (
        df.groupby("cause")
        .agg(events=("long_event", "size"),
             long_events=("long_event", "sum"),
             median_hours=("duration_hours", "median"))
        .assign(long_rate=lambda d: (d["long_events"] / d["events"]).round(3))
        .sort_values("events", ascending=False)
    )
    by_cause.round(2).to_csv(OUTPUT_DIR / "cause_summary.csv")

    print(f"\nwrote {len(df):,} events x {len(df.columns)} columns -> {DATASET_PATH}")
    print(f"\nmedian restoration: {df['duration_hours'].median():.1f} h")
    print(f"'long' = over {LONG_HOURS} h\n")
    print(df.groupby("split")["long_event"].agg(["size", "sum", "mean"]).round(3).to_string())
    print("\nby cause:")
    print(by_cause.round(2).to_string())


if __name__ == "__main__":
    main()

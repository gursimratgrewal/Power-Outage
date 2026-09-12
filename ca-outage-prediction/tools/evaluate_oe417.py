"""Evaluate the DOE OE-417 grid disruption data as an outage source.

    python tools/evaluate_oe417.py

Reproduces the counts behind notes/data-source-evaluation.md, which is why
this project uses EAGLE-I instead. Reads the file committed at
handoff/oe417/grid_disruption_2000_2014.csv.gz.

The question this answers: if the target were "a major grid disturbance was
reported in California today", how many positive days would there be to
train and test on?
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import HANDOFF_DIR  # noqa: E402

SOURCE = HANDOFF_DIR / "oe417" / "grid_disruption_2000_2014.csv.gz"

# Event descriptions are free text -- 90 distinct spellings for 162 California
# events -- so causes are bucketed by keyword rather than by any code column.
PATTERNS = {
    "storm/wind/rain": r"storm|weather|wind|rain|lightning|snow|ice|flood|hurricane|tornado|thunder",
    "heat": r"heat|high temperature",
    "fire": r"fire|wild land|brush",
}
WEATHER_DRIVEN = list(PATTERNS)

TEST_FROM = 2012  # matches the project's "hold out the last three years"


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE} not found.")

    df = pd.read_csv(SOURCE)
    print(f"all events: {len(df):,} ({df.Year.min()}-{df.Year.max()}, nationwide)")

    ca = df[df["Geographic Areas"].fillna("").str.contains("California", case=False)].copy()
    ca["date"] = pd.to_datetime(ca["Date Event Began"], errors="coerce")
    ca = ca.dropna(subset=["date"])

    # Most specific label wins: a brush fire that caused load shedding is a
    # fire, not an "other".
    description = ca["Event Description"].str.lower()
    ca["cause"] = "other (equipment, attack, fuel, grid operations)"
    for label in ("fire", "heat", "storm/wind/rain"):
        ca.loc[description.str.contains(PATTERNS[label], regex=True), "cause"] = label

    print(f"California: {len(ca)} events on {ca['date'].nunique()} distinct days\n")

    summary = (
        ca.groupby("cause")
        .agg(events=("date", "size"), days=("date", "nunique"))
        .sort_values("events", ascending=False)
    )
    print(summary.to_string())

    weather = ca[ca["cause"].isin(WEATHER_DRIVEN)]
    span_days = (ca["date"].max() - ca["date"].min()).days

    print(f"\nweather-driven: {len(weather)} events on {weather['date'].nunique()} days")
    print(f"base rate, any CA event      : {ca['date'].nunique() / span_days:.2%}")
    print(f"base rate, weather-driven only: {weather['date'].nunique() / span_days:.2%}")

    held_out = weather[weather["date"].dt.year >= TEST_FROM]["date"].nunique()
    print(f"\npositive days in a {TEST_FROM}-2014 test set: {held_out}")
    print(
        f"\nVERDICT: {held_out} positives is far too few to measure precision@10 or\n"
        "PR-AUC with any stability -- one event would move the metric by more than\n"
        "ten points. See notes/data-source-evaluation.md."
    )


if __name__ == "__main__":
    main()

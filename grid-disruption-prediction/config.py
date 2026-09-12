"""Paths, split dates and target definition."""

from pathlib import Path

from states import END_DATE, POINTS, START_DATE, STATE_POINTS  # noqa: F401

PROJECT_ROOT = Path(__file__).resolve().parent

RAW_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FIGURE_DIR = OUTPUT_DIR / "figures"

HANDOFF_DIR = PROJECT_ROOT / "handoff"
HANDOFF_WEATHER_DIR = HANDOFF_DIR / "openmeteo"

for _d in (RAW_DIR, INTERIM_DIR, PROCESSED_DIR, OUTPUT_DIR, FIGURE_DIR, HANDOFF_WEATHER_DIR):
    _d.mkdir(parents=True, exist_ok=True)

OE417_PATH = HANDOFF_DIR / "oe417" / "grid_disruption_2000_2014.csv.gz"

STATES = sorted(STATE_POINTS)

# Event descriptions are free text, so causes are bucketed by keyword. Only
# these count as weather-driven; everything else (equipment failure,
# vandalism, fuel supply, islanding) is excluded from the target, because
# weather has no business predicting it.
CAUSE_PATTERNS = {
    "storm/wind/rain": (
        r"storm|weather|wind|rain|lightning|snow|ice|flood|hurricane|tornado|thunder"
    ),
    "heat": r"heat|high temperature",
    "fire": r"fire|wild land|brush",
}

# Time-based split: twelve years to train, the last three held out.
TRAIN_END = "2011-12-31"
TEST_START = "2012-01-01"

FEATURES = [
    "gust_max",
    "gust_max_lag1",
    "wind_max",
    "temp_mean",
    "temp_max",
    "precip_max",
    "precip_lag1",
    "gust_3d_mean",
    "gust_7d_mean",
    "precip_3d_sum",
    "precip_7d_sum",
    "temp_7d_mean",
    "days_since_rain",
    "month",
    "day_of_week",
    "state",
]
CATEGORICAL = ["month", "day_of_week", "state"]
NUMERIC = [f for f in FEATURES if f not in CATEGORICAL]

# Days an operations team would staff up for, nationwide, in the test window.
K_VALUES = [10, 25, 50, 100]

RANDOM_STATE = 42

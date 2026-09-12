"""Shared configuration: paths, target definition, split, feature list."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FIGURE_DIR = OUTPUT_DIR / "figures"

for _d in (PROCESSED_DIR, OUTPUT_DIR, FIGURE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

SOURCE_PATH = DATA_DIR / "grid_disruption_2000_2014.csv.gz"
DATASET_PATH = PROCESSED_DIR / "events.csv"

# A "long" event is one still unresolved 24 hours after it began. That's the
# line where restoration stops being a shift's work and becomes a multi-day
# mutual-aid problem, and it sits near the middle of the distribution
# (median restoration is about 11 hours) so both classes are well populated.
LONG_HOURS = 24

# Durations beyond 30 days are data-entry errors, not month-long outages.
MAX_PLAUSIBLE_HOURS = 24 * 30

# Time-based split: twelve years to learn from, the last three held out.
TRAIN_END_YEAR = 2011
TEST_START_YEAR = 2012

# Event Description is free text -- 700+ distinct spellings -- so causes are
# bucketed by keyword. Order matters: the first pattern that matches wins,
# so the most specific causes are listed first.
CAUSE_PATTERNS = [
    ("fire", r"fire|wild ?land|brush"),
    ("heat/demand", r"heat|high temperature|public appeal|load shed|shed load|inadequa|demand"),
    ("storm", r"storm|weather|wind|rain|lightning|snow|ice|flood|hurricane|tornado|thunder"),
    ("attack", r"attack|vandal|sabotage|cyber|theft|suspicious"),
    ("fuel supply", r"fuel supply|fuel deficiency|natural gas|coal|hydro"),
    ("equipment", r"equipment|transformer|breaker|cable|switch|relay|unit trip|plant trip|faulted"),
    ("system operations", r"islanding|separation|interruption|transmission|substation|voltage"),
]
OTHER_CAUSE = "other"

FEATURES = [
    "cause",
    "nerc_region",
    "month",
    "hour_began",
    "day_of_week",
    "n_areas",
    "events_region_7d",
    "events_region_30d",
    "events_national_30d",
]
CATEGORICAL = ["cause", "nerc_region", "month"]
NUMERIC = [f for f in FEATURES if f not in CATEGORICAL]

# How many events an operations team could realistically pre-stage crews for
# in the three-year test window.
K_VALUES = [10, 25, 50, 100]

RANDOM_STATE = 42

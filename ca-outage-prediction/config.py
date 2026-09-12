"""Shared configuration: counties, paths, date splits, target definition."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

RAW_DIR = PROJECT_ROOT / "data" / "raw"
EAGLEI_DIR = RAW_DIR / "eaglei"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FIGURE_DIR = OUTPUT_DIR / "figures"

# Unlike data/, handoff/ is committed: it's where hand-downloaded files go
# when the machine running the pipeline can't reach the data sources itself.
# See handoff/README.md.
HANDOFF_DIR = PROJECT_ROOT / "handoff"
HANDOFF_EAGLEI_DIR = HANDOFF_DIR / "eaglei"
HANDOFF_WEATHER_DIR = HANDOFF_DIR / "openmeteo"

for _d in (EAGLEI_DIR, INTERIM_DIR, PROCESSED_DIR, OUTPUT_DIR, FIGURE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# 15 California counties, mostly PG&E service territory plus two southern
# counties for contrast. Lat/lon are approximate county centroids -- one
# weather point per county, which is the main spatial simplification here.
COUNTIES = [
    {"county": "Alameda", "fips": 6001, "lat": 37.65, "lon": -121.92},
    {"county": "Butte", "fips": 6007, "lat": 39.67, "lon": -121.60},
    {"county": "Contra Costa", "fips": 6013, "lat": 37.92, "lon": -121.95},
    {"county": "El Dorado", "fips": 6017, "lat": 38.78, "lon": -120.52},
    {"county": "Fresno", "fips": 6019, "lat": 36.76, "lon": -119.65},
    {"county": "Humboldt", "fips": 6023, "lat": 40.70, "lon": -123.87},
    {"county": "Los Angeles", "fips": 6037, "lat": 34.31, "lon": -118.23},
    {"county": "Napa", "fips": 6055, "lat": 38.51, "lon": -122.33},
    {"county": "Nevada", "fips": 6057, "lat": 39.30, "lon": -120.77},
    {"county": "Placer", "fips": 6061, "lat": 39.06, "lon": -120.72},
    {"county": "Sacramento", "fips": 6067, "lat": 38.45, "lon": -121.34},
    {"county": "San Diego", "fips": 6073, "lat": 33.03, "lon": -116.77},
    {"county": "Santa Clara", "fips": 6085, "lat": 37.23, "lon": -121.69},
    {"county": "Shasta", "fips": 6089, "lat": 40.76, "lon": -122.04},
    {"county": "Sonoma", "fips": 6097, "lat": 38.53, "lon": -122.89},
]

FIPS_TO_COUNTY = {c["fips"]: c["county"] for c in COUNTIES}

# EAGLE-I coverage starts in 2014. Adjust END_DATE to whatever years you
# actually downloaded.
START_DATE = "2014-01-01"
END_DATE = "2024-12-31"

# Time-based split. Everything on or before TRAIN_END trains; everything on
# or after TEST_START is held out. Never shuffle -- see README.
TRAIN_END = "2021-12-31"
TEST_START = "2022-01-01"

# "High outage day" = a day in the top 5% of peak customers out *for that
# county*. Per-county so that Los Angeles and Napa each get a threshold on
# their own scale. Thresholds are computed on training years only.
HIGH_OUTAGE_QUANTILE = 0.95

# Model inputs. All of them come from weather, so the model can be run on
# tomorrow's forecast -- nothing here needs tomorrow's outage data.
FEATURES = [
    "gust_max",
    "gust_max_lag1",
    "wind_max",
    "temp_mean",
    "temp_max",
    "precip",
    "precip_lag1",
    "gust_3d_mean",
    "gust_7d_mean",
    "precip_3d_sum",
    "precip_7d_sum",
    "temp_7d_mean",
    "days_since_rain",
    "month",
    "day_of_week",
]

# Number of worst days an ops team would staff up for, used for precision@k.
K_VALUES = [10, 25, 50, 100]

RANDOM_STATE = 42

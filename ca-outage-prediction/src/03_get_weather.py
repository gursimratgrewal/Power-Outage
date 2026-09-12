"""Step 3: pull daily weather history for each county centroid.

Source: Open-Meteo historical archive API (free, no key required).
Output: data/interim/weather_daily.csv

One request per county, cached to data/raw/weather/<county>.csv so re-runs
don't re-hit the API. Pass --refresh to ignore the cache.
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import COUNTIES, END_DATE, INTERIM_DIR, RAW_DIR, START_DATE  # noqa: E402

API_URL = "https://archive-api.open-meteo.com/v1/archive"
CACHE_DIR = RAW_DIR / "weather"
OUT_PATH = INTERIM_DIR / "weather_daily.csv"

DAILY_VARS = [
    "wind_gusts_10m_max",
    "wind_speed_10m_max",
    "temperature_2m_mean",
    "temperature_2m_max",
    "precipitation_sum",
]

MAX_RETRIES = 4
PAUSE_SECONDS = 2.0


def fetch_county(county: dict) -> pd.DataFrame:
    params = {
        "latitude": county["lat"],
        "longitude": county["lon"],
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": ",".join(DAILY_VARS),
        "timezone": "America/Los_Angeles",
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(API_URL, params=params, timeout=60)
            response.raise_for_status()
            payload = response.json()
            break
        except (requests.RequestException, ValueError) as err:
            wait = 2**attempt
            if attempt == MAX_RETRIES - 1:
                raise SystemExit(f"{county['county']}: giving up after {err}")
            print(f"  {county['county']}: {err} -- retrying in {wait}s")
            time.sleep(wait)

    df = pd.DataFrame(payload["daily"]).rename(columns={"time": "date"})
    df["county"] = county["county"]
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="ignore cached files")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    frames = []

    for county in COUNTIES:
        cache_path = CACHE_DIR / f"{county['county'].replace(' ', '_').lower()}.csv"
        if cache_path.exists() and not args.refresh:
            print(f"{county['county']}: cached")
            frames.append(pd.read_csv(cache_path))
            continue

        print(f"{county['county']}: fetching {START_DATE}..{END_DATE}")
        df = fetch_county(county)
        df.to_csv(cache_path, index=False)
        frames.append(df)
        time.sleep(PAUSE_SECONDS)  # be polite to a free API

    weather = pd.concat(frames, ignore_index=True)
    weather["date"] = pd.to_datetime(weather["date"])
    weather = weather.sort_values(["county", "date"])
    weather.to_csv(OUT_PATH, index=False)

    missing = weather[DAILY_VARS].isna().mean().round(4)
    print(f"\nwrote {len(weather):,} county-days -> {OUT_PATH}")
    print("missing rate by variable:")
    print(missing)


if __name__ == "__main__":
    main()

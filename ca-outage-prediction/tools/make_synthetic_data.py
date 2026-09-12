"""Generate fake data so the pipeline can be smoke-tested without downloads.

This exists ONLY so you can check that steps 01-05 run end to end on a
machine with no EAGLE-I download and no internet. The numbers it produces
are invented. Nothing it writes belongs in the README results table.

It writes:
  data/raw/eaglei/eaglei_outages_<year>.csv   (same columns as the real files)
  data/raw/weather/<county>.csv               (same columns as step 03's cache)

so steps 01, 02, 04 and 05 run for real and step 03 reads the cache instead
of calling Open-Meteo.

    python tools/make_synthetic_data.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import COUNTIES, EAGLEI_DIR, END_DATE, RAW_DIR, START_DATE  # noqa: E402

WEATHER_DIR = RAW_DIR / "weather"
RNG = np.random.default_rng(0)


def fake_weather(county: dict, dates: pd.DatetimeIndex) -> pd.DataFrame:
    doy = dates.dayofyear.to_numpy()
    winter = np.cos(2 * np.pi * (doy - 15) / 365)  # +1 in January, -1 in July

    temp_mean = 15 - 8 * winter + RNG.normal(0, 2.5, len(dates))
    temp_max = temp_mean + RNG.uniform(4, 10, len(dates))

    wet = RNG.random(len(dates)) < (0.10 + 0.22 * np.clip(winter, 0, None))
    precip = np.where(wet, RNG.exponential(9, len(dates)), 0.0).round(2)

    storm = RNG.random(len(dates)) < (0.03 + 0.05 * np.clip(winter, 0, None))
    gust = 28 + 6 * winter + RNG.gamma(2, 3, len(dates)) + storm * RNG.uniform(25, 60, len(dates))

    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "wind_gusts_10m_max": gust.round(1),
            "wind_speed_10m_max": (gust * 0.6).round(1),
            "temperature_2m_mean": temp_mean.round(1),
            "temperature_2m_max": temp_max.round(1),
            "precipitation_sum": precip,
            "county": county["county"],
        }
    )


def fake_outages(county: dict, weather: pd.DataFrame, size: int) -> pd.DataFrame:
    """Outages driven by gusts and rain, with plenty of noise."""
    gust = weather["wind_gusts_10m_max"].to_numpy()
    precip = weather["precipitation_sum"].to_numpy()

    intensity = (
        0.02 * np.clip(gust - 35, 0, None) ** 1.6
        + 0.35 * np.clip(precip - 3, 0, None)
        + RNG.gamma(1.2, 0.8, len(gust))
    )
    peak = (intensity * size * 0.002 * RNG.lognormal(0, 0.7, len(gust))).round()

    rows = []
    for date, value in zip(pd.to_datetime(weather["date"]), peak):
        if value <= 0:
            continue
        # Spread the day's outage over a handful of 15-minute intervals.
        n_intervals = int(RNG.integers(4, 16))
        start_hour = int(RNG.integers(0, 20))
        shape = np.sin(np.linspace(0.2, np.pi - 0.2, n_intervals))
        for i, weight in enumerate(shape):
            rows.append(
                {
                    "fips_code": county["fips"],
                    "county": county["county"],
                    "state": "California",
                    "sum": int(max(1, value * weight)),
                    "run_start_time": date
                    + pd.Timedelta(hours=start_hour, minutes=15 * i),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range(START_DATE, END_DATE, freq="D")

    all_outages = []
    for county in COUNTIES:
        weather = fake_weather(county, dates)
        weather.to_csv(
            WEATHER_DIR / f"{county['county'].replace(' ', '_').lower()}.csv", index=False
        )
        # Rough stand-in for "how many customers this county has".
        size = int(RNG.integers(30_000, 900_000))
        all_outages.append(fake_outages(county, weather, size))
        print(f"{county['county']}: synthetic weather + outages")

    outages = pd.concat(all_outages, ignore_index=True)
    for year, group in outages.groupby(outages["run_start_time"].dt.year):
        path = EAGLEI_DIR / f"eaglei_outages_{year}.csv"
        group.to_csv(path, index=False)
        print(f"{path.name}: {len(group):,} rows")

    print("\nSynthetic data written. These numbers are made up -- smoke test only.")


if __name__ == "__main__":
    main()

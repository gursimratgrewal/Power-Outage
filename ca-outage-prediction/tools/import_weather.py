"""Import Open-Meteo weather downloaded by hand instead of by step 03.

Use this when the machine running the pipeline can't reach the Open-Meteo
API: download the archive response in a browser, drop the file(s) in
data/raw/openmeteo/ (or handoff/openmeteo/), and run

    python tools/import_weather.py

It accepts either format the API returns:

  * CSV  (&format=csv) -- one file, all locations, in stacked blocks
  * JSON (the default) -- one file per county, or one file holding a list

Each response carries its own latitude/longitude, so counties are matched by
coordinates and the file names don't matter. Output goes to
data/interim/weather_daily.csv plus the per-county cache in
data/raw/weather/, so step 03 becomes a no-op on later runs.
"""

import io
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import COUNTIES, HANDOFF_WEATHER_DIR, INTERIM_DIR, RAW_DIR  # noqa: E402

# Downloads are picked up from either place.
DROP_DIRS = [RAW_DIR / "openmeteo", HANDOFF_WEATHER_DIR]
CACHE_DIR = RAW_DIR / "weather"
OUT_PATH = INTERIM_DIR / "weather_daily.csv"

# How far a response's coordinates may sit from a configured centroid before
# we assume it isn't one of our counties at all. ~0.2 degrees is ~20 km.
MAX_DEGREES = 0.2

UNIT_SUFFIX = re.compile(r"\s*\(.*\)$")


def match_county(lat: float, lon: float) -> str:
    best = min(COUNTIES, key=lambda c: (c["lat"] - lat) ** 2 + (c["lon"] - lon) ** 2)
    distance = max(abs(best["lat"] - lat), abs(best["lon"] - lon))
    if distance > MAX_DEGREES:
        raise SystemExit(
            f"({lat}, {lon}) is {distance:.2f} deg from the nearest configured "
            f"county ({best['county']}). Did this come from a different request?"
        )
    return best["county"]


def parse_csv(text: str) -> list[pd.DataFrame]:
    """Open-Meteo CSV: metadata block, then data block, repeated per location."""
    blocks = [b for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    frames, pending = [], None

    for block in blocks:
        lines = block.strip().splitlines()
        header = lines[0].lower()

        if header.startswith("latitude"):
            meta = pd.read_csv(io.StringIO(block))
            pending = (float(meta["latitude"].iloc[0]), float(meta["longitude"].iloc[0]))
        elif header.startswith("time"):
            if pending is None:
                raise SystemExit("found a data block before any latitude/longitude block")
            df = pd.read_csv(io.StringIO(block))
            df.columns = [UNIT_SUFFIX.sub("", c).strip() for c in df.columns]
            df = df.rename(columns={"time": "date"})
            df["county"] = match_county(*pending)
            frames.append(df)
            pending = None

    if not frames:
        raise SystemExit("no data blocks found -- is this really an Open-Meteo CSV?")
    return frames


def parse_json(text: str) -> list[pd.DataFrame]:
    payload = json.loads(text)
    responses = payload if isinstance(payload, list) else [payload]

    frames = []
    for response in responses:
        if "daily" not in response:
            raise SystemExit(f"response has no 'daily' block: {list(response)[:6]}")
        df = pd.DataFrame(response["daily"]).rename(columns={"time": "date"})
        df["county"] = match_county(
            float(response["latitude"]), float(response["longitude"])
        )
        frames.append(df)
    return frames


def main() -> None:
    DROP_DIRS[0].mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(
        p
        for d in DROP_DIRS
        if d.exists()
        for p in d.iterdir()
        if p.suffix.lower() in {".csv", ".json"}
    )
    if not files:
        where = " or ".join(str(d) for d in DROP_DIRS)
        raise SystemExit(f"Put the downloaded Open-Meteo file(s) in {where} first.")

    frames = []
    for path in files:
        text = path.read_text()
        parsed = parse_json(text) if path.suffix.lower() == ".json" else parse_csv(text)
        print(f"{path.name}: {len(parsed)} location(s) -- "
              f"{', '.join(sorted(f['county'].iloc[0] for f in parsed))}")
        frames.extend(parsed)

    weather = pd.concat(frames, ignore_index=True)
    weather["date"] = pd.to_datetime(weather["date"])
    weather = weather.sort_values(["county", "date"]).drop_duplicates(["county", "date"])

    for county, group in weather.groupby("county"):
        cache = CACHE_DIR / f"{county.replace(' ', '_').lower()}.csv"
        group.to_csv(cache, index=False)

    weather.to_csv(OUT_PATH, index=False)

    have = set(weather["county"])
    missing = [c["county"] for c in COUNTIES if c["county"] not in have]
    print(f"\nwrote {len(weather):,} county-days for {len(have)} counties -> {OUT_PATH}")
    print(f"dates {weather['date'].min().date()} .. {weather['date'].max().date()}")
    if missing:
        print(f"WARNING: no weather for {', '.join(missing)}")


if __name__ == "__main__":
    main()

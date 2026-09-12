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

import gzip
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
    """Open-Meteo CSV: a metadata block, then a data block.

    Two shapes turn up. A single-location request writes one metadata row and
    a data block keyed by `time`. A multi-location request writes one metadata
    row per location and a data block with a `location_id` column joining back
    to it. Both are handled; a multi-location file may also arrive as repeated
    single-location block pairs.
    """
    blocks = [b for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    frames, coords = [], {}

    for block in blocks:
        header = block.strip().splitlines()[0].lower()

        if "latitude" in header:
            meta = pd.read_csv(io.StringIO(block))
            if "location_id" in meta.columns:
                coords = {
                    int(r.location_id): (float(r.latitude), float(r.longitude))
                    for r in meta.itertuples()
                }
            else:
                coords = {None: (float(meta["latitude"].iloc[0]), float(meta["longitude"].iloc[0]))}
            continue

        if not header.startswith(("time", "location_id")):
            continue

        if not coords:
            raise SystemExit("found a data block before any latitude/longitude block")

        df = pd.read_csv(io.StringIO(block))
        df.columns = [UNIT_SUFFIX.sub("", c).strip() for c in df.columns]
        df = df.rename(columns={"time": "date"})

        if "location_id" in df.columns:
            for location_id, group in df.groupby("location_id"):
                if int(location_id) not in coords:
                    raise SystemExit(f"location_id {location_id} has no metadata row")
                group = group.drop(columns="location_id").copy()
                group["county"] = match_county(*coords[int(location_id)])
                frames.append(group)
        else:
            df["county"] = match_county(*next(iter(coords.values())))
            frames.append(df)
        coords = {}

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


def _kind(path: Path) -> str | None:
    """csv / json for a file we can read, else None. Handles .gz."""
    suffixes = [s.lower() for s in path.suffixes]
    if suffixes and suffixes[-1] == ".gz":
        suffixes = suffixes[:-1]
    if not suffixes:
        return None
    return {".csv": "csv", ".json": "json"}.get(suffixes[-1])


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".gz":
        with gzip.open(path, "rt") as handle:
            return handle.read()
    return path.read_text()


def main() -> None:
    DROP_DIRS[0].mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(
        p
        for d in DROP_DIRS
        if d.exists()
        for p in d.iterdir()
        if _kind(p) is not None
    )
    if not files:
        where = " or ".join(str(d) for d in DROP_DIRS)
        raise SystemExit(f"Put the downloaded Open-Meteo file(s) in {where} first.")

    frames = []
    for path in files:
        text = read_text(path)
        parsed = parse_json(text) if _kind(path) == "json" else parse_csv(text)
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

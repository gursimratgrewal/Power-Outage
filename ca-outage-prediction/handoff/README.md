# handoff/ — hand-downloaded data drop

This folder exists for the case where the machine running the pipeline can't
reach the data sources itself (locked-down network, sandbox, CI runner). Download
the files on a machine that *can*, drop them here, commit, and the pipeline picks
them up automatically — `src/01_filter_outages.py` and `tools/import_weather.py`
both search `handoff/` as well as `data/`.

Unlike `data/`, this folder is **not** gitignored, so whatever you put here gets
committed. Keep it small: GitHub warns above 50 MB per file and rejects above
100 MB.

---

## 1. Outages → `handoff/eaglei/`

**Source: EAGLE-I, Oak Ridge National Laboratory.** County-level customers-out
every 15 minutes, 2014 onward, one CSV per year.

It's published on **OSTI**, one record per year, each with its own DOI. Search
[osti.gov](https://www.osti.gov/search) for **"EAGLE-I Power Outage Data"** and
take every year from 2014 through 2024.

The 2025 record, as a worked example of what you're looking for:

| field | value |
| --- | --- |
| title | EAGLE-I Power Outage Data 2025 |
| DOI | `10.13139/ORNLNCCS/3012826` |
| landing page | `https://www.osti.gov/biblio/3012826` |
| direct download | `https://www.osti.gov/servlets/purl/3012826` |
| publisher | Oak Ridge National Laboratory, for DOE CESER |

**2025 on its own is not enough** — this project trains on 2014–2021 and tests on
2022–2024, so the years matter more than any single file.

> OSTI is unreachable from the sandbox this was written in, so the per-year DOIs
> for 2014–2024 couldn't be looked up. The 2025 row above is confirmed from the
> dataset's own metadata record; the others follow the same pattern.

The full dataset is several GB — **too big to commit raw.** Pick one:

**Option A (smallest, preferred).** Filter to the 15 configured counties first,
then commit only that:

```bash
pip install pandas
mkdir -p data/raw/eaglei && mv ~/Downloads/eaglei_outages_*.csv data/raw/eaglei/
python src/01_filter_outages.py
gzip -c data/interim/outages_15min.csv > handoff/eaglei/outages_15min.csv.gz
```

Step 01 recognises `outages_15min.csv[.gz]` as already-filtered and skips
straight past the raw files on the next run.

**Option B.** Commit the yearly files gzipped, if they're small enough after
compression:

```bash
for f in ~/Downloads/eaglei_outages_*.csv; do
  gzip -c "$f" > "handoff/eaglei/$(basename "$f").gz"
done
```

**Option C (no Python).** If `fips_code` is the first column — check the header
first — grep the California counties out directly:

```bash
head -1 eaglei_outages_2014.csv > handoff/eaglei/outages_15min.csv
cat eaglei_outages_*.csv \
  | grep -E '^(6001|6007|6013|6017|6019|6023|6037|6055|6057|6061|6067|6073|6085|6089|6097),' \
  >> handoff/eaglei/outages_15min.csv
gzip handoff/eaglei/outages_15min.csv
```

Expected columns either way:

| column | meaning |
| --- | --- |
| `fips_code` | county FIPS (`6001`–`6115` for California) |
| `sum` *or* `customers_out` | customers without power in that 15-minute interval |
| `run_start_time` | interval timestamp |

---

## 2. Weather → `handoff/openmeteo/`

**Source: Open-Meteo historical archive API.** Free, no key, no sign-up. Open
this URL in a browser and save the file it returns — it covers **all 15 counties
in one request** (about 60,000 rows, a few MB):

```
https://archive-api.open-meteo.com/v1/archive?latitude=37.65,39.67,37.92,38.78,36.76,40.7,34.31,38.51,39.3,39.06,38.45,33.03,37.23,40.76,38.53&longitude=-121.92,-121.6,-121.95,-120.52,-119.65,-123.87,-118.23,-122.33,-120.77,-120.72,-121.34,-116.77,-121.69,-122.04,-122.89&start_date=2014-01-01&end_date=2024-12-31&daily=wind_gusts_10m_max,wind_speed_10m_max,temperature_2m_mean,temperature_2m_max,precipitation_sum&timezone=America/Los_Angeles&format=csv
```

**This is already done** — `open-meteo-ca-counties-2014-2024.csv.gz` in this folder
holds all 15 counties for 2014-01-01 to 2024-12-31, 60,270 county-days with no
missing values. The URL above is kept for regenerating it.

Save the download to `handoff/openmeteo/` (`.gz` is fine), then:

```bash
python tools/import_weather.py
```

Drop `&format=csv` and you get JSON instead — the importer reads either, and
matches each response to a county by its coordinates, so file names don't
matter. Per-county downloads work too; just put all the files in this folder.

If you change the county list in `config.py`, regenerate the URL rather than
editing it by hand: the latitude and longitude lists have to stay in the same
order.

---

## After the files are in place

```bash
python src/01_filter_outages.py    # reads handoff/eaglei/
python src/02_aggregate_daily.py
python tools/import_weather.py     # reads handoff/openmeteo/, replaces step 03
python src/04_build_features.py
python src/05_train_evaluate.py
python tools/fill_results.py
```

# ca-outage-prediction

**Can weather forecasts tell you which California counties will have a bad outage day tomorrow?**

Daily power-outage records for 15 California counties, joined to daily weather at each
county's centroid, used to flag the days that land in the worst 5% of outages for that
county. The point is a ranking an operations team could actually act on: *these are the
ten county-days next week worth staffing up for.*

This is a prediction problem, not a causal one. Nothing here claims wind *causes* a
particular outage — only that wind measured the same day is informative about how bad
that day turns out to be.

---

## Data

**Outages — EAGLE-I (Oak Ridge National Laboratory).** County-level customers-out,
recorded every 15 minutes, 2014 onward. Published as one CSV per year. Search for
"EAGLE-I power outage data ORNL" (DOI `10.13139/ORNLNCCS/1975202`, hosted on DOE's
Constellation repository) and download the yearly files into `data/raw/eaglei/`.

`src/01_filter_outages.py` globs `eaglei_outages_*.csv` and expects these columns:

| column | meaning |
| --- | --- |
| `fips_code` | county FIPS (California counties are `6001`–`6115`) |
| `sum` | customers without power in that 15-minute interval |
| `run_start_time` | interval timestamp |

If the release you download names the count column `customers_out` instead, the script
handles both.

**Weather — Open-Meteo historical archive API.** Free, no API key. One request per
county centroid, pulling daily max wind gust, max wind speed, mean and max temperature,
and precipitation total. Responses are cached in `data/raw/weather/` so re-runs don't
re-hit the API. If the API isn't reachable, `handoff/README.md` has a single URL that
returns all 15 counties, and `tools/import_weather.py` loads the saved file.

**Counties (15).** Alameda, Butte, Contra Costa, El Dorado, Fresno, Humboldt, Los
Angeles, Napa, Nevada, Placer, Sacramento, San Diego, Santa Clara, Shasta, Sonoma —
mostly PG&E territory, with two southern counties for contrast. Centroids are in
`config.py`; edit that list to change the sample.

---

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# put the EAGLE-I yearly CSVs in data/raw/eaglei/ first
./run_all.sh
```

Or step by step:

```bash
python src/01_filter_outages.py    # raw EAGLE-I -> our 15 counties
python src/02_aggregate_daily.py   # 15-minute records -> one row per county-day
python src/03_get_weather.py       # Open-Meteo, one call per county
python src/04_build_features.py    # join, rolling features, target
python src/05_train_evaluate.py    # three models, metrics, calibration, figures
python tools/fill_results.py       # paste the results table into this README
```

**Can't reach the data sources from the machine running this?** Download the files
somewhere else, drop them in `handoff/`, and the pipeline picks them up —
`handoff/README.md` has the exact sources, the one-URL Open-Meteo link for all 15
counties, and how to keep the EAGLE-I files small enough to commit. Use
`python tools/import_weather.py` in place of step 03.

No internet and no EAGLE-I download at all? `python tools/make_synthetic_data.py` writes
fake files in the same formats so you can check the pipeline runs. **Its numbers are
invented** — useful for a smoke test, useless as a result.

---

## Method

### Target

A **high outage day** is a county-day in the top 5% of `peak_customers_out` *for that
county*. Per-county thresholds keep Los Angeles and Napa on their own scales; a day
that's routine in LA would be the worst week of the year in Napa.

The threshold is computed on the **training years only**. Taking the 95th percentile
over all years would let the test period's own extremes set the bar it's graded
against.

Peak customers out is the target rather than customer-hours because it's the simpler
quantity and the one that maps to "how many crews do we need on shift."

### Features

All 15 inputs come from weather, so the model can be run tomorrow morning on a
forecast. Nothing is derived from past outage counts.

| feature | why |
| --- | --- |
| `gust_max`, `wind_max` | wind brings down lines and throws branches into them |
| `gust_max_lag1` | yesterday's wind — damage that shows up as an outage the next day |
| `gust_3d_mean`, `gust_7d_mean` | a sustained windy stretch, not one gusty afternoon |
| `precip`, `precip_lag1` | rain today and yesterday |
| `precip_3d_sum`, `precip_7d_sum` | saturated ground, which is how wind topples trees |
| `temp_mean`, `temp_max`, `temp_7d_mean` | heat drives load, and load drives equipment failure |
| `days_since_rain` | length of the dry spell — dry fuel plus wind is the PSPS combination |
| `month`, `day_of_week` | season, and any weekday pattern in reporting |

Rolling windows include the current day, which is legitimate here: every day inside a
3- or 7-day window is either already past or covered by the same forecast.

### Validation

**Train on 2014–2021, test on 2022–2024. The split is by date, never random.**

A random split would put January 2023 in training and February 2023 in test. Storms
span days and weather is autocorrelated, so the model would be scored on conditions it
had effectively already seen, and every number would come out flattering. Time-based
splitting is the only honest option for a forecasting problem, and it's also the only
one that matches how the model would be used: fit on history, run on tomorrow.

### Models

1. **Baseline** — always predict "not a high outage day."
2. **Logistic regression** — scaled numeric features, one-hot month and day of week.
3. **Gradient boosting** — 300 trees, depth 3, learning rate 0.05.

The operating threshold for the two real models isn't 0.5. It's set so the model flags
the same share of days that the training years actually were high — otherwise the
threshold just reflects how imbalanced the data is.

### Metrics

**Accuracy is not one of them, except to make a point.** The baseline that never
predicts anything scores about 95%, because 95% of days aren't high-outage days. Any
metric a do-nothing model wins is the wrong metric.

What's reported instead:

- **Precision and recall** at the operating threshold — of the days we flagged, how
  many were bad; of the bad days, how many did we catch.
- **PR-AUC** — threshold-free ranking quality on a rare event. No-skill is the base
  rate (≈0.05), not 0.5.
- **Precision@k** for k = 10, 25, 50, 100 — of the k worst-looking county-days, how
  many really were high-outage days. This is the number an operations team cares
  about, because k is a staffing budget. The baseline has no ranking, so its
  precision@k is the base rate: what you'd get picking k days at random.

---

## Results

Empty until you run the pipeline on real data. After `05_train_evaluate.py`, run
`python tools/fill_results.py` and this table fills itself in from
`outputs/model_comparison.csv`.

<!-- RESULTS:START -->

| model | accuracy | precision | recall | PR-AUC | P@10 | P@25 | P@50 | P@100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline (never high) | | | | | | | | |
| logistic regression | | | | | | | | |
| gradient boosting | | | | | | | | |

<!-- RESULTS:END -->

The full set of outputs:

| file | contents |
| --- | --- |
| `outputs/model_comparison.csv` | the table above, all metrics |
| `outputs/precision_at_k.csv` | precision@k for every model and k |
| `outputs/calibration.csv` | decile calibration for the best-ranking model |
| `outputs/feature_importance.csv` | gradient boosting importances |
| `outputs/test_predictions.csv` | test-year scores, sorted worst-first |
| `outputs/target_summary.csv` | high-day counts per county and split |
| `outputs/figures/` | PR curve, calibration plot, feature importance |

`outputs/` is gitignored so synthetic smoke-test results can't be committed by
accident. After a real run, commit the tables and figures you want to show.

### Calibration

Predictions are bucketed into deciles and mean predicted probability is compared
against the observed rate of high-outage days in each bucket
(`outputs/calibration.csv`, `outputs/figures/calibration.png`).

This matters because a ranking alone doesn't tell you what to do. If the model says
20% and those days really do go bad 20% of the time, "20%" is a number you can put in
front of an operations manager. If it says 20% and they go bad 60% of the time, the
ranking may still be fine but the probability is decoration.

---

## Limitations

Honest list, because these would be the first questions from anyone who works with
this data:

- **Outage counts reflect utility reporting, not physical reality.** EAGLE-I scrapes
  utility outage maps. Coverage, refresh rate, and what counts as "out" differ by
  utility and have changed over time, so a level shift between years may be a
  reporting change rather than a grid change.
- **A storm outage and a PSPS shutoff look identical here.** A Public Safety Power
  Shutoff is a deliberate de-energization during dangerous fire weather. It shows up in
  the data as a large outage on a hot windy day — exactly the signal the model learns.
  Some of the model's skill on high-wind days is likely learning *utility decisions*,
  not equipment failures. Separating them needs PSPS event records, which aren't here.
- **County-level is coarse.** A county gets one weather point at its centroid. Sonoma
  County spans coast to inland ridgeline; one gust reading doesn't describe both.
- **No asset data.** Nothing about circuit age, conductor type, vegetation, or
  undergrounding. The model knows weather and nothing about the grid it's hitting.
- **Missing days are treated as zero.** EAGLE-I records intervals with customers out,
  so a county-day with no rows is read as a quiet day. A genuine data-collection gap is
  indistinguishable from a quiet day and gets scored as one.
- **Weather is observed history, not forecasts.** Training on Open-Meteo reanalysis and
  deploying on a real forecast would lose some skill to forecast error. The honest
  version of this test re-runs it on archived forecasts.
- **15 counties, ~11 years.** At a 5% positive rate that's a few thousand high days.
  Enough to fit these models; not enough to chase a complicated one.

---

## Repo layout

```
ca-outage-prediction/
├── config.py                    counties, centroids, dates, split, feature list
├── requirements.txt
├── run_all.sh
├── src/
│   ├── 01_filter_outages.py     raw EAGLE-I -> our counties
│   ├── 02_aggregate_daily.py    15-min -> county-day peak and customer-hours
│   ├── 03_get_weather.py        Open-Meteo, cached per county
│   ├── 04_build_features.py     join, rolling features, target definition
│   └── 05_train_evaluate.py     three models, metrics, calibration, figures
├── tools/
│   ├── import_weather.py        load hand-downloaded Open-Meteo files
│   ├── make_synthetic_data.py   fake data for an offline smoke test
│   └── fill_results.py          writes the results table into the README
├── handoff/                     committed drop folder for downloaded data
├── data/                        gitignored
└── outputs/                     gitignored
```

#!/usr/bin/env bash
# Run the whole pipeline. Assumes the EAGLE-I files are already in
# data/raw/eaglei/ (see README).
set -euo pipefail
cd "$(dirname "$0")"

python src/01_filter_outages.py
python src/02_aggregate_daily.py
python src/03_get_weather.py
python src/04_build_features.py
python src/05_train_evaluate.py
python tools/fill_results.py

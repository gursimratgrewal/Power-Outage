#!/usr/bin/env bash
# Everything, end to end. No downloads -- the data is in data/.
set -euo pipefail
cd "$(dirname "$0")"

python src/01_build_dataset.py
python src/02_train_evaluate.py
python tools/fill_results.py

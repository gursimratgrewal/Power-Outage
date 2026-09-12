"""Paste the real results into the README after a run.

    python tools/fill_results.py

Reads outputs/model_comparison.csv and rewrites the table between the
RESULTS markers in README.md. Run it after 05_train_evaluate.py so the
README shows what the models actually did instead of an empty table.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import K_VALUES, OUTPUT_DIR, PROJECT_ROOT  # noqa: E402

START = "<!-- RESULTS:START -->"
END = "<!-- RESULTS:END -->"

LABELS = {
    "baseline_never_high": "baseline (never high)",
    "logistic": "logistic regression",
    "gradient_boosting": "gradient boosting",
}


def build_table(comparison: pd.DataFrame) -> str:
    k_cols = [f"precision@{k}" for k in K_VALUES if f"precision@{k}" in comparison]
    header = ["model", "accuracy", "precision", "recall", "PR-AUC"]
    header += [f"P@{c.split('@')[1]}" for c in k_cols]

    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    for _, row in comparison.iterrows():
        cells = [LABELS.get(row["model"], row["model"])]
        cells += [f"{row[c]:.3f}" for c in ("accuracy", "precision", "recall", "pr_auc")]
        cells += [f"{row[c]:.3f}" for c in k_cols]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readme", type=Path, default=PROJECT_ROOT / "README.md")
    parser.add_argument("--comparison", type=Path, default=OUTPUT_DIR / "model_comparison.csv")
    args = parser.parse_args()

    if not args.comparison.exists():
        raise SystemExit(f"{args.comparison} not found -- run 05_train_evaluate.py first.")

    table = build_table(pd.read_csv(args.comparison))
    text = args.readme.read_text()

    if START not in text or END not in text:
        raise SystemExit(f"{args.readme} is missing the {START} / {END} markers.")

    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    args.readme.write_text(f"{head}{START}\n\n{table}\n\n{END}{tail}")

    print(f"updated the results table in {args.readme}")
    print(table)


if __name__ == "__main__":
    main()

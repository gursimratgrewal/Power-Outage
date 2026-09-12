"""Step 2: train on 2000-2011, test on 2012-2014, compare three models.

Input : data/processed/events.csv
Output: outputs/*.csv, outputs/figures/*.png

Models, in increasing order of effort:
  1. baseline    -- always predict "not long"
  2. logistic    -- logistic regression
  3. gradient_boosting

The split is by date, never random. Grid disturbances cluster: one storm
system produces several reports across several utilities within days. A
random split would put some of those reports in training and their siblings
in test, and the model would be scored on events it had effectively already
seen. Splitting by year is also the only version that matches how it would
be used -- fit on history, score the event now on the desk.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import (  # noqa: E402
    CATEGORICAL,
    DATASET_PATH,
    FEATURES,
    FIGURE_DIR,
    K_VALUES,
    LONG_HOURS,
    NUMERIC,
    OUTPUT_DIR,
    RANDOM_STATE,
)

TARGET = "long_event"


def precision_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Of the k events we'd pre-stage crews for, how many really ran long?"""
    k = min(k, len(scores))
    top = np.argsort(-scores, kind="stable")[:k]
    return float(y_true[top].mean())


def evaluate(name: str, y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    y_pred = (scores >= threshold).astype(int)
    row = {
        "model": name,
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "pr_auc": average_precision_score(y_true, scores),
        "roc_auc": roc_auc_score(y_true, scores) if scores.std() > 0 else 0.5,
        "flagged": int(y_pred.sum()),
    }
    for k in K_VALUES:
        row[f"precision@{k}"] = precision_at_k(y_true, scores, k)
    return row


def calibration_table(y_true: np.ndarray, scores: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """If it says 70%, do 70% of those events actually run long?"""
    df = pd.DataFrame({"y": y_true, "p": scores})
    df["decile"] = pd.qcut(df["p"].rank(method="first"), bins, labels=False) + 1
    return (
        df.groupby("decile")
        .agg(events=("y", "size"), predicted_rate=("p", "mean"), actual_rate=("y", "mean"))
        .reset_index()
        .round(4)
    )


def main() -> None:
    if not DATASET_PATH.exists():
        raise SystemExit(f"{DATASET_PATH} not found -- run 01_build_dataset.py first.")

    df = pd.read_csv(DATASET_PATH, parse_dates=["began"])
    train, test = df[df["split"] == "train"], df[df["split"] == "test"]

    X_train, y_train = train[FEATURES], train[TARGET].to_numpy()
    X_test, y_test = test[FEATURES], test[TARGET].to_numpy()

    base_rate = y_train.mean()
    print(f"train {train['year'].min()}-{train['year'].max()}: {len(train):,} events, "
          f"{y_train.sum():,} long ({base_rate:.1%})")
    print(f"test  {test['year'].min()}-{test['year'].max()}: {len(test):,} events, "
          f"{y_test.sum():,} long ({y_test.mean():.1%})")

    preprocessor = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC),
            # sparse_output=False: HistGradientBoosting requires dense input.
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
        ]
    )

    models = {
        "logistic": Pipeline(
            [("prep", preprocessor),
             ("clf", LogisticRegression(max_iter=3000, random_state=RANDOM_STATE))]
        ),
        "gradient_boosting": Pipeline(
            [("prep", preprocessor),
             ("clf", HistGradientBoostingClassifier(
                 max_iter=300, learning_rate=0.05, max_depth=3,
                 min_samples_leaf=20, random_state=RANDOM_STATE))]
        ),
    }

    # Baseline: never call an event long. No ranking, so its precision@k is
    # the base rate -- what you'd get picking k events blind.
    rows = [{
        "model": "baseline_never_long",
        "accuracy": 1 - y_test.mean(),
        "precision": 0.0, "recall": 0.0, "f1": 0.0,
        "pr_auc": float(y_test.mean()), "roc_auc": 0.5, "flagged": 0,
        **{f"precision@{k}": float(y_test.mean()) for k in K_VALUES},
    }]

    scores_by_model, fitted = {}, {}
    for name, model in models.items():
        print(f"\nfitting {name} ...")
        model.fit(X_train, y_train)
        fitted[name] = model

        # Operating threshold: flag the same share of events that the training
        # years actually ran long, rather than an arbitrary 0.5.
        train_scores = model.predict_proba(X_train)[:, 1]
        threshold = float(np.quantile(train_scores, 1 - base_rate))

        scores = model.predict_proba(X_test)[:, 1]
        scores_by_model[name] = scores
        row = evaluate(name, y_test, scores, threshold)
        row["threshold"] = round(threshold, 4)
        rows.append(row)

    comparison = pd.DataFrame(rows).round(4)
    comparison.to_csv(OUTPUT_DIR / "model_comparison.csv", index=False)
    print("\n=== model comparison (2012-2014) ===")
    print(comparison.to_string(index=False))

    pk = [{"model": n, "k": k, "precision_at_k": precision_at_k(y_test, s, k)}
          for n, s in scores_by_model.items() for k in K_VALUES]
    pk += [{"model": "random_pick", "k": k, "precision_at_k": float(y_test.mean())}
           for k in K_VALUES]
    pd.DataFrame(pk).round(4).to_csv(OUTPUT_DIR / "precision_at_k.csv", index=False)

    best = max(scores_by_model, key=lambda n: average_precision_score(y_test, scores_by_model[n]))
    calib = calibration_table(y_test, scores_by_model[best])
    calib.insert(0, "model", best)
    calib.to_csv(OUTPUT_DIR / "calibration.csv", index=False)
    print(f"\n=== calibration deciles ({best}) ===")
    print(calib.to_string(index=False))

    print("\ncomputing permutation importance ...")
    result = permutation_importance(
        fitted[best], X_test, y_test, scoring="average_precision",
        n_repeats=10, random_state=RANDOM_STATE,
    )
    importance = (
        pd.DataFrame({"feature": FEATURES, "importance": result.importances_mean})
        .sort_values("importance", ascending=False)
        .round(4)
    )
    importance.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False)
    print(f"\n=== permutation importance ({best}, drop in PR-AUC when shuffled) ===")
    print(importance.to_string(index=False))

    preds = test[["began", "cause", "nerc_region", "geographic_areas",
                  "duration_hours", TARGET]].copy()
    for name, scores in scores_by_model.items():
        preds[f"score_{name}"] = scores.round(4)
    preds.sort_values(f"score_{best}", ascending=False).to_csv(
        OUTPUT_DIR / "test_predictions.csv", index=False
    )

    # ---- figures ------------------------------------------------------------
    plt.figure(figsize=(6, 4.5))
    for name, scores in scores_by_model.items():
        precision, recall, _ = precision_recall_curve(y_test, scores)
        plt.plot(recall, precision,
                 label=f"{name} (PR-AUC {average_precision_score(y_test, scores):.3f})")
    plt.axhline(y_test.mean(), ls="--", c="grey", label=f"no skill ({y_test.mean():.3f})")
    plt.xlabel("recall")
    plt.ylabel("precision")
    plt.title(f"Predicting events lasting over {LONG_HOURS}h, 2012-2014")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "precision_recall.png", dpi=150)
    plt.close()

    plt.figure(figsize=(5, 5))
    plt.plot(calib["predicted_rate"], calib["actual_rate"], "o-", label=best)
    plt.plot([0, 1], [0, 1], ls="--", c="grey", label="perfect calibration")
    plt.xlabel("mean predicted probability")
    plt.ylabel("observed share running long")
    plt.title("Calibration by decile, 2012-2014")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "calibration.png", dpi=150)
    plt.close()

    top = importance.iloc[::-1]
    plt.figure(figsize=(6, 4.5))
    plt.barh(top["feature"], top["importance"])
    plt.xlabel("drop in PR-AUC when shuffled")
    plt.title("Permutation importance")
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "feature_importance.png", dpi=150)
    plt.close()

    print(f"\nwrote tables to {OUTPUT_DIR} and figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()

"""Step 5: train three models on the early years, test on the late ones.

Input : data/processed/model_table.csv
Output: outputs/model_comparison.csv, outputs/precision_at_k.csv,
        outputs/calibration.csv, outputs/feature_importance.csv,
        outputs/test_predictions.csv, outputs/figures/*.png

Models, in increasing order of effort:
  1. baseline    -- always say "not a high outage day"
  2. logistic    -- logistic regression on the weather features
  3. gradient_boosting

The split is by date, never random. Random splitting would put January 2023
in training and February 2023 in test, and a winter storm spans both -- the
model would be scored on weather it had already seen.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import GradientBoostingClassifier  # noqa: E402
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
    FEATURES,
    FIGURE_DIR,
    K_VALUES,
    OUTPUT_DIR,
    PROCESSED_DIR,
    RANDOM_STATE,
)

CATEGORICAL = ["month", "day_of_week"]
NUMERIC = [f for f in FEATURES if f not in CATEGORICAL]

TABLE_PATH = PROCESSED_DIR / "model_table.csv"
TARGET = "high_outage_day"


def precision_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Of the k days we'd staff up for, what fraction were really bad days?"""
    k = min(k, len(scores))
    top = np.argsort(-scores, kind="stable")[:k]
    return float(y_true[top].mean())


def evaluate(name: str, y_true: np.ndarray, scores: np.ndarray, threshold: float):
    y_pred = (scores >= threshold).astype(int)
    row = {
        "model": name,
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "pr_auc": average_precision_score(y_true, scores),
        "roc_auc": roc_auc_score(y_true, scores) if scores.std() > 0 else 0.5,
        "flagged_days": int(y_pred.sum()),
    }
    for k in K_VALUES:
        row[f"precision@{k}"] = precision_at_k(y_true, scores, k)
    return row


def calibration_table(y_true: np.ndarray, scores: np.ndarray, bins: int = 10):
    """Bucket predictions into deciles: if it says 20%, does it happen 20%?"""
    df = pd.DataFrame({"y": y_true, "p": scores})
    df["decile"] = pd.qcut(df["p"].rank(method="first"), bins, labels=False) + 1
    table = (
        df.groupby("decile")
        .agg(days=("y", "size"), predicted_rate=("p", "mean"), actual_rate=("y", "mean"))
        .reset_index()
    )
    return table.round(4)


def main() -> None:
    if not TABLE_PATH.exists():
        raise SystemExit(f"{TABLE_PATH} not found -- run 04_build_features.py first.")

    df = pd.read_csv(TABLE_PATH, parse_dates=["date"])
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]

    X_train, y_train = train[FEATURES], train[TARGET].to_numpy()
    X_test, y_test = test[FEATURES], test[TARGET].to_numpy()

    base_rate = y_train.mean()
    print(f"train: {len(train):,} county-days, {y_train.sum():,} high ({base_rate:.1%})")
    print(f"test : {len(test):,} county-days, {y_test.sum():,} high ({y_test.mean():.1%})")
    print(f"train years {train['date'].dt.year.min()}-{train['date'].dt.year.max()}, "
          f"test years {test['date'].dt.year.min()}-{test['date'].dt.year.max()}")

    preprocessor = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ]
    )

    models = {
        "logistic": Pipeline(
            [
                ("prep", preprocessor),
                ("clf", LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)),
            ]
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=3,
            subsample=0.9,
            random_state=RANDOM_STATE,
        ),
    }

    # Baseline: always "not a high day". No ranking, so its precision@k is
    # what you'd get picking k days at random -- the base rate.
    rows = [
        {
            "model": "baseline_never_high",
            "accuracy": 1 - y_test.mean(),
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "pr_auc": float(y_test.mean()),
            "roc_auc": 0.5,
            "flagged_days": 0,
            **{f"precision@{k}": float(y_test.mean()) for k in K_VALUES},
        }
    ]

    scores_by_model, fitted = {}, {}
    for name, model in models.items():
        print(f"\nfitting {name} ...")
        model.fit(X_train, y_train)
        fitted[name] = model

        # Operating threshold: flag the same share of days the training years
        # actually were high. Picking 0.5 out of the air would just reflect
        # how imbalanced the data is.
        train_scores = model.predict_proba(X_train)[:, 1]
        threshold = float(np.quantile(train_scores, 1 - base_rate))

        scores = model.predict_proba(X_test)[:, 1]
        scores_by_model[name] = scores
        row = evaluate(name, y_test, scores, threshold)
        row["threshold"] = round(threshold, 4)
        rows.append(row)

    comparison = pd.DataFrame(rows).round(4)
    comparison.to_csv(OUTPUT_DIR / "model_comparison.csv", index=False)
    print("\n=== model comparison (test years) ===")
    print(comparison.to_string(index=False))

    # ---- precision@k detail -------------------------------------------------
    pk_rows = []
    for name, scores in scores_by_model.items():
        for k in K_VALUES:
            pk_rows.append(
                {"model": name, "k": k, "precision_at_k": precision_at_k(y_test, scores, k)}
            )
    for k in K_VALUES:
        pk_rows.append({"model": "random_pick", "k": k, "precision_at_k": float(y_test.mean())})
    pd.DataFrame(pk_rows).round(4).to_csv(OUTPUT_DIR / "precision_at_k.csv", index=False)

    # ---- calibration of the best-ranking model ------------------------------
    best = max(scores_by_model, key=lambda n: average_precision_score(y_test, scores_by_model[n]))
    calib = calibration_table(y_test, scores_by_model[best])
    calib.insert(0, "model", best)
    calib.to_csv(OUTPUT_DIR / "calibration.csv", index=False)
    print(f"\n=== calibration deciles ({best}) ===")
    print(calib.to_string(index=False))

    # ---- feature importance -------------------------------------------------
    gb = fitted["gradient_boosting"]
    importance = (
        pd.DataFrame({"feature": FEATURES, "importance": gb.feature_importances_})
        .sort_values("importance", ascending=False)
        .round(4)
    )
    importance.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False)
    print("\n=== gradient boosting feature importance ===")
    print(importance.to_string(index=False))

    # ---- predictions --------------------------------------------------------
    preds = test[["county", "date", "peak_customers_out", TARGET]].copy()
    for name, scores in scores_by_model.items():
        preds[f"score_{name}"] = scores.round(4)
    preds.sort_values(f"score_{best}", ascending=False).to_csv(
        OUTPUT_DIR / "test_predictions.csv", index=False
    )

    # ---- figures ------------------------------------------------------------
    plt.figure(figsize=(6, 4.5))
    for name, scores in scores_by_model.items():
        precision, recall, _ = precision_recall_curve(y_test, scores)
        ap = average_precision_score(y_test, scores)
        plt.plot(recall, precision, label=f"{name} (PR-AUC {ap:.3f})")
    plt.axhline(y_test.mean(), ls="--", c="grey", label=f"no skill ({y_test.mean():.3f})")
    plt.xlabel("recall")
    plt.ylabel("precision")
    plt.title("Precision-recall, test years")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "precision_recall.png", dpi=150)
    plt.close()

    plt.figure(figsize=(5, 5))
    plt.plot(calib["predicted_rate"], calib["actual_rate"], "o-", label=best)
    lim = max(calib["predicted_rate"].max(), calib["actual_rate"].max()) * 1.1
    plt.plot([0, lim], [0, lim], ls="--", c="grey", label="perfect calibration")
    plt.xlabel("mean predicted probability")
    plt.ylabel("observed rate of high-outage days")
    plt.title("Calibration by decile, test years")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "calibration.png", dpi=150)
    plt.close()

    top = importance.head(10).iloc[::-1]
    plt.figure(figsize=(6, 4.5))
    plt.barh(top["feature"], top["importance"])
    plt.xlabel("gradient boosting importance")
    plt.title("Top features")
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "feature_importance.png", dpi=150)
    plt.close()

    print(f"\nwrote tables to {OUTPUT_DIR} and figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()

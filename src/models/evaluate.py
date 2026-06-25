"""Standalone evaluator + feature-importance helper used by the
dissertation. Loads the saved best model and produces:
    - residual scatter plot
    - feature importance bar chart (where supported)
    - error distribution histogram

Run:
    python -m src.models.evaluate
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from src.pipeline.feature_engineering import features_target

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLEANED = PROJECT_ROOT / "data" / "cleaned" / "listings.csv"
MODEL = PROJECT_ROOT / "src" / "models" / "best_model.pkl"
QUANTILES = PROJECT_ROOT / "src" / "models" / "quantile_models.pkl"
FIG_DIR = PROJECT_ROOT / "docs" / "screenshots"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    if not (CLEANED.exists() and MODEL.exists()):
        raise SystemExit("Run preprocess + train first.")

    df = pd.read_csv(CLEANED)
    pipe = joblib.load(MODEL)

    X, y = features_target(df)
    _, X_te, _, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    preds = pipe.predict(X_te)
    residuals = y_te - preds

    # 1. Predicted vs Actual
    plt.figure(figsize=(7, 7))
    plt.scatter(y_te, preds, alpha=0.25, s=8)
    lo, hi = min(y_te.min(), preds.min()), max(y_te.max(), preds.max())
    plt.plot([lo, hi], [lo, hi], "r--", lw=1)
    plt.xlabel("Actual price (£)")
    plt.ylabel("Predicted price (£)")
    plt.title("Predicted vs Actual — best model")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "predicted_vs_actual.png", dpi=140)
    plt.close()

    # 2. Residual distribution
    plt.figure(figsize=(8, 5))
    plt.hist(residuals, bins=60)
    plt.xlabel("Residual (£)  [actual - predicted]")
    plt.ylabel("Count")
    plt.title("Residual distribution")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "residuals.png", dpi=140)
    plt.close()

    # 3. Feature importance (if the underlying model exposes it)
    final_estimator = pipe.named_steps.get("model")
    if hasattr(final_estimator, "feature_importances_"):
        preprocessor = pipe.named_steps["preprocess"]
        feat_names = preprocessor.get_feature_names_out()
        importances = final_estimator.feature_importances_
        # Top 20 only — full list goes to JSON
        order = np.argsort(importances)[::-1]
        top = order[:20]

        plt.figure(figsize=(9, 7))
        plt.barh(np.array(feat_names)[top][::-1], importances[top][::-1])
        plt.xlabel("Importance")
        plt.title("Top 20 features by importance")
        plt.tight_layout()
        plt.savefig(FIG_DIR / "feature_importance.png", dpi=140)
        plt.close()

        ranking = sorted(
            zip(feat_names.tolist(), importances.tolist()),
            key=lambda t: t[1], reverse=True,
        )
        (PROJECT_ROOT / "docs" / "feature_importance.json").write_text(
            json.dumps(ranking[:50], indent=2)
        )

    # 4. Prediction interval — does the 80% band capture real prices?
    if QUANTILES.exists():
        qm = joblib.load(QUANTILES)
        # a readable sample of the test set, sorted by predicted price
        rng = np.random.default_rng(42)
        idx = rng.choice(len(X_te), size=min(80, len(X_te)), replace=False)
        Xs = X_te.iloc[idx]
        actual = y_te.iloc[idx].to_numpy()
        mid = qm["mid"].predict(Xs)
        lo = qm["low"].predict(Xs)
        hi = qm["high"].predict(Xs)
        order = np.argsort(mid)
        actual, lo, mid, hi = actual[order], lo[order], mid[order], hi[order]
        inside = (actual >= lo) & (actual <= hi)
        coverage = inside.mean() * 100
        xs = np.arange(len(mid))

        plt.figure(figsize=(10, 5))
        plt.fill_between(xs, lo, hi, color="#10b981", alpha=0.18,
                         label="80% prediction interval")
        plt.plot(xs, mid, color="#0f172a", lw=1, label="Predicted (median)")
        plt.scatter(xs[inside], actual[inside], s=14, color="#0f766e",
                    label="Actual (inside band)", zorder=3)
        plt.scatter(xs[~inside], actual[~inside], s=18, color="#e11d48",
                    label="Actual (outside band)", zorder=3)
        plt.xlabel("Test cars (sorted by predicted price)")
        plt.ylabel("Price (£)")
        plt.title(f"80% prediction interval — empirical coverage {coverage:.1f}%")
        plt.legend(fontsize=8, loc="upper left")
        plt.tight_layout()
        plt.savefig(FIG_DIR / "prediction_interval.png", dpi=140)
        plt.close()
        print(f"[evaluate] interval chart coverage on sample: {coverage:.1f}%")

    print(f"[evaluate] wrote charts to {FIG_DIR}")


if __name__ == "__main__":
    main()

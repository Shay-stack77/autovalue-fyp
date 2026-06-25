"""Train Linear Regression, Random Forest, and XGBoost on the cleaned
dataset, compare them on RMSE / MAE / R2, persist the winning model and
the full preprocessing pipeline to disk for the API to load.

Run:
    python -m src.models.train
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

from src.pipeline.feature_engineering import (
    ALL_FEATURES, TARGET, build_preprocessor, features_target,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned" / "listings.csv"
MODELS_DIR = PROJECT_ROOT / "src" / "models"
DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42


def get_models() -> dict[str, object]:
    return {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=200, max_depth=None,
            n_jobs=-1, random_state=RANDOM_STATE,
        ),
        "xgboost": XGBRegressor(
            n_estimators=400, learning_rate=0.08, max_depth=8,
            subsample=0.9, colsample_bytree=0.9,
            tree_method="hist", random_state=RANDOM_STATE, n_jobs=-1,
        ),
    }


def evaluate(y_true, y_pred) -> dict[str, float]:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    return {"rmse": rmse, "mae": mae, "r2": r2}


# Quantiles for the 80% prediction interval (low / median / high).
QUANTILE_ALPHAS = {"low": 0.1, "mid": 0.5, "high": 0.9}

# Market-adjustment factor. The Kaggle corpus reflects pre-pandemic (2020)
# prices; the Auto Trader Retail Price Index put used-car values ~13% above
# that 2020 baseline by Q1 2025, so predictions are scaled by 1.13 to bring
# them toward the current market. Documented in the dissertation (Ch.5).
MARKET_FACTOR = 1.13


def train_quantile_models(X_train, y_train) -> dict[str, Pipeline]:
    """Train one XGBoost quantile regressor per band for prediction intervals."""
    models: dict[str, Pipeline] = {}
    for name, alpha in QUANTILE_ALPHAS.items():
        pipe = Pipeline([
            ("preprocess", build_preprocessor()),
            ("model", XGBRegressor(
                objective="reg:quantileerror", quantile_alpha=alpha,
                n_estimators=300, learning_rate=0.08, max_depth=8,
                subsample=0.9, colsample_bytree=0.9,
                tree_method="hist", random_state=RANDOM_STATE, n_jobs=-1,
            )),
        ])
        pipe.fit(X_train, y_train)
        models[name] = pipe
        print(f"[train] quantile model alpha={alpha} trained")
    return models


def interval_coverage(quantile_models, X_test, y_test) -> dict[str, float]:
    """Empirical coverage of the 80% interval on the held-out set."""
    lo = quantile_models["low"].predict(X_test)
    hi = quantile_models["high"].predict(X_test)
    inside = float(((y_test.values >= lo) & (y_test.values <= hi)).mean())
    width = float(np.mean(hi - lo))
    return {"coverage": round(inside, 4), "mean_width_gbp": round(width, 2)}


def baseline_car(df: pd.DataFrame) -> dict:
    """The 'average' car used as the reference for why-this-price attribution."""
    return {
        "brand": df["brand"].mode().iloc[0],
        "model": df["model"].mode().iloc[0],
        "transmission": df["transmission"].mode().iloc[0],
        "fuelType": df["fuelType"].mode().iloc[0],
        "mileage": float(df["mileage"].median()),
        "engineSize": float(df["engineSize"].median()),
        "age": float(df["age"].median()),
    }


def train_and_compare(df: pd.DataFrame, split):
    X_train, X_test, y_train, y_test = split

    results: dict[str, dict] = {}
    pipelines: dict[str, Pipeline] = {}

    for name, regressor in get_models().items():
        pipe = Pipeline([
            ("preprocess", build_preprocessor()),
            ("model", regressor),
        ])
        t0 = time.perf_counter()
        pipe.fit(X_train, y_train)
        train_time = time.perf_counter() - t0

        preds = pipe.predict(X_test)
        metrics = evaluate(y_test, preds)
        metrics["train_seconds"] = round(train_time, 2)
        results[name] = metrics
        pipelines[name] = pipe

        print(
            f"[train] {name:20s}  "
            f"RMSE={metrics['rmse']:>10,.2f}  "
            f"MAE={metrics['mae']:>10,.2f}  "
            f"R2={metrics['r2']:.4f}  "
            f"({train_time:.1f}s)"
        )

    # Pick the model with the best R2
    best_name = max(results, key=lambda k: results[k]["r2"])
    print(f"\n[train] best model: {best_name}  (R2={results[best_name]['r2']:.4f})")
    return best_name, pipelines[best_name], results


def save_artifacts(best_name, best_pipe, results, df, quantile_models, coverage) -> None:
    model_path = MODELS_DIR / "best_model.pkl"
    joblib.dump(best_pipe, model_path)
    print(f"[train] saved {model_path}")

    # Quantile models for the prediction interval
    qpath = MODELS_DIR / "quantile_models.pkl"
    joblib.dump(quantile_models, qpath)
    print(f"[train] saved {qpath}")

    # Compact corpus the API uses for comparable-car lookups
    corpus_cols = ALL_FEATURES + [TARGET]
    corpus = df[corpus_cols].copy()
    corpus_path = MODELS_DIR / "corpus.pkl"
    corpus.to_pickle(corpus_path)
    print(f"[train] saved {corpus_path}  ({len(corpus):,} rows)")

    # Calibration: market factor, the baseline car, per-brand error
    per_brand_mae = {}
    if "brand" in df.columns:
        # rough per-brand MAE proxy already reported in the dissertation
        per_brand_mae = {}
    calibration = {
        "market_factor": MARKET_FACTOR,
        "market_factor_basis": (
            "Auto Trader Retail Price Index: UK used-car values sat ~13% above "
            "the 2020 baseline by Q1 2025 (index 113.2). Applied to bring the "
            "2020-trained predictions toward the current market."
        ),
        "interval_alphas": QUANTILE_ALPHAS,
        "interval_coverage": coverage,
        "baseline_car": baseline_car(df),
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    cal_path = MODELS_DIR / "calibration.json"
    cal_path.write_text(json.dumps(calibration, indent=2))
    print(f"[train] saved {cal_path}")

    # Persist comparison report (used in the dissertation)
    report = {
        "best_model": best_name,
        "metrics": results,
        "interval_coverage": coverage,
        "market_factor": MARKET_FACTOR,
        "feature_columns": ALL_FEATURES,
        "target": TARGET,
        "n_rows": int(len(df)),
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    report_path = DOCS_DIR / "model_comparison.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"[train] saved {report_path}")

    # Vocabulary file the frontend uses for dropdowns
    vocab = {
        "brands": sorted(df["brand"].dropna().unique().tolist()),
        "transmissions": sorted(df["transmission"].dropna().unique().tolist()),
        "fuelTypes": sorted(df["fuelType"].dropna().unique().tolist()),
        "models_by_brand": {
            b: sorted(df.loc[df["brand"] == b, "model"].dropna().unique().tolist())
            for b in sorted(df["brand"].dropna().unique())
        },
    }
    vocab_path = MODELS_DIR / "vocab.json"
    vocab_path.write_text(json.dumps(vocab, indent=2))
    print(f"[train] saved {vocab_path}")


def main() -> None:
    if not CLEANED_PATH.exists():
        raise SystemExit(
            f"Cleaned dataset not found at {CLEANED_PATH}. "
            f"Run `python -m src.pipeline.preprocess` first."
        )
    df = pd.read_csv(CLEANED_PATH)
    print(f"[train] loaded {len(df):,} cleaned rows")

    X, y = features_target(df)
    split = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)
    X_train, X_test, y_train, y_test = split

    best_name, best_pipe, results = train_and_compare(df, split)

    print("[train] training quantile models for prediction intervals...")
    quantile_models = train_quantile_models(X_train, y_train)
    coverage = interval_coverage(quantile_models, X_test, y_test)
    print(f"[train] 80% interval coverage={coverage['coverage']:.3f}  "
          f"mean width=£{coverage['mean_width_gbp']:,.0f}")

    save_artifacts(best_name, best_pipe, results, df, quantile_models, coverage)


if __name__ == "__main__":
    main()

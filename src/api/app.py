"""Flask API exposing the valuation engine.

Endpoints:
    GET  /health          -> liveness probe + which features are loaded
    GET  /vocab           -> dropdown options for the frontend
    POST /predict         -> full valuation report for a single vehicle:
                             estimate, 80% range, deal rating (if an asking
                             price is supplied), why-this-price breakdown,
                             5-year depreciation forecast and comparable cars

Run:
    python -m src.api.app
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from src.pipeline.feature_engineering import ALL_FEATURES
from src.models.insights import ValuationEngine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "src" / "models"
MODEL_PATH = MODELS_DIR / "best_model.pkl"
QUANTILE_PATH = MODELS_DIR / "quantile_models.pkl"
CORPUS_PATH = MODELS_DIR / "corpus.pkl"
CALIBRATION_PATH = MODELS_DIR / "calibration.json"
VOCAB_PATH = MODELS_DIR / "vocab.json"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

REQUIRED_INPUT_KEYS = {
    "brand", "model", "year", "mileage",
    "transmission", "fuelType", "engineSize",
}


def _build_engine():
    """Assemble the ValuationEngine from whatever artifacts are present."""
    if not MODEL_PATH.exists():
        return None
    point_model = joblib.load(MODEL_PATH)

    quantile_models = {}
    if QUANTILE_PATH.exists():
        quantile_models = joblib.load(QUANTILE_PATH)

    if CORPUS_PATH.exists():
        corpus = pd.read_pickle(CORPUS_PATH)
    else:
        corpus = pd.DataFrame(columns=ALL_FEATURES + ["price"])

    market_factor = 1.0
    baseline = None
    if CALIBRATION_PATH.exists():
        cal = json.loads(CALIBRATION_PATH.read_text())
        market_factor = float(cal.get("market_factor", 1.0))
        baseline = cal.get("baseline_car")

    return ValuationEngine(
        point_model=point_model,
        quantile_models=quantile_models,
        corpus=corpus,
        market_factor=market_factor,
        baseline_car=baseline,
    )


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    # SR3: restrict the CORS policy to the verbs the frontend actually uses.
    CORS(app, methods=["GET", "POST"])

    app.config["ENGINE"] = _build_engine()
    app.config["VOCAB"] = (
        json.loads(VOCAB_PATH.read_text()) if VOCAB_PATH.exists() else {}
    )

    @app.get("/health")
    def health():
        engine = app.config["ENGINE"]
        return jsonify(
            status="ok",
            model_loaded=engine is not None,
            features={
                "interval": bool(engine and engine.quantile_models),
                "comparables": bool(engine is not None and not engine.corpus.empty),
                "market_factor": engine.market_factor if engine else 1.0,
            },
        )

    @app.get("/vocab")
    def vocab():
        return jsonify(app.config.get("VOCAB", {}))

    def _parse_row(payload):
        """Validate input and build the feature row. Returns (row, error)."""
        missing = REQUIRED_INPUT_KEYS - payload.keys()
        if missing:
            return None, f"Missing fields: {sorted(missing)}"
        try:
            year = int(payload["year"])
            mileage = float(payload["mileage"])
            engine_size = float(payload["engineSize"])
        except (TypeError, ValueError):
            return None, "year/mileage/engineSize must be numeric."
        row = {
            "brand": payload["brand"],
            "model": payload["model"],
            "transmission": payload["transmission"],
            "fuelType": payload["fuelType"],
            "mileage": mileage,
            "engineSize": engine_size,
            "age": 2025 - year,
        }
        return row, None

    @app.post("/predict")
    def predict():
        engine = app.config["ENGINE"]
        if engine is None:
            return jsonify(error="Model not trained yet."), 503

        payload = request.get_json(silent=True) or {}
        row, err = _parse_row(payload)
        if err:
            return jsonify(error=err), 400

        asking_price = payload.get("askingPrice")
        try:
            asking_price = float(asking_price) if asking_price not in (None, "") else None
        except (TypeError, ValueError):
            asking_price = None

        report = engine.full_report(row, asking_price=asking_price)
        # Backwards-compatible field for the original tests/clients
        report["predicted_price"] = report["estimate"]
        return jsonify(report)

    # Serve the static frontend so the whole app runs from one origin
    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:asset>")
    def asset(asset: str):
        return send_from_directory(FRONTEND_DIR, asset)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)

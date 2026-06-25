"""ValuationEngine — turns the trained models into a buying assistant.

The base regressor predicts a single price. This module wraps it with the
features that make the artefact a decision tool rather than a number:

    * prediction intervals      (quantile regression, low / median / high)
    * a market-adjustment factor (brings 2020-trained prices to the current market)
    * a CarGurus-style deal rating (Great / Good / Fair / High / Overpriced)
    * a "why this price" breakdown (counterfactual feature attribution)
    * a depreciation forecast    (model-driven projected value over 5 years)
    * comparable cars            (nearest neighbours from the training corpus)

Everything here is dependency-light and deterministic so it is easy to test
and safe to demonstrate live.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.pipeline.feature_engineering import (
    ALL_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES,
)

# UK Driver and Vehicle Licensing Agency average annual mileage, used to age
# a car realistically in the depreciation forecast.
AVG_MILES_PER_YEAR = 10_000
REFERENCE_YEAR = 2025      # the corpus 'age' was computed as 2025 - registration year
FORECAST_BASE_YEAR = 2026  # the depreciation forecast starts from the current year

# CarGurus-style deal-rating bands, expressed as (asking - estimate) / estimate.
# Source: CarGurus Instant Market Value deal ratings.
DEAL_BANDS = [
    (-0.10, "great", "Great deal"),     # 10%+ below estimate
    (-0.05, "good", "Good deal"),       # 5-10% below
    (0.05, "fair", "Fair price"),       # within +-5%
    (0.10, "high", "Priced high"),      # 5-10% above
]
DEAL_OVER = ("overpriced", "Overpriced")  # more than 10% above


@dataclass
class ValuationEngine:
    """Wraps the point model, the quantile models and the corpus."""

    point_model: Any
    quantile_models: dict[str, Any]          # {"low": pipe, "mid": pipe, "high": pipe}
    corpus: pd.DataFrame                      # cleaned listings with ALL_FEATURES + price
    market_factor: float = 1.0
    baseline_car: dict[str, Any] | None = None

    # ---------- low-level helpers ---------------------------------------
    def _row_frame(self, row: dict[str, Any]) -> pd.DataFrame:
        """Build the single-row feature frame the pipelines expect."""
        return pd.DataFrame([{k: row[k] for k in ALL_FEATURES}])[ALL_FEATURES]

    def _raw_point(self, row: dict[str, Any]) -> float:
        return float(self.point_model.predict(self._row_frame(row))[0])

    def _adjust(self, value: float) -> float:
        """Apply the market factor and floor at zero."""
        return max(value * self.market_factor, 0.0)

    # ---------- 1. point + interval -------------------------------------
    def predict(self, row: dict[str, Any]) -> dict[str, float]:
        """Return the market-adjusted point estimate and an 80% interval."""
        point = self._adjust(self._raw_point(row))
        out = {"point": round(point, 2)}
        if self.quantile_models:
            frame = self._row_frame(row)
            lo = self._adjust(float(self.quantile_models["low"].predict(frame)[0]))
            hi = self._adjust(float(self.quantile_models["high"].predict(frame)[0]))
            # guard against quantile crossing
            lo, hi = min(lo, hi), max(lo, hi)
            out["low"] = round(lo, 2)
            out["high"] = round(hi, 2)
        return out

    # ---------- 2. deal rating ------------------------------------------
    def deal_rating(self, asking_price: float, estimate: float) -> dict[str, Any]:
        """Compare an asking price to our estimate (CarGurus-style bands)."""
        if estimate <= 0:
            return {"rating": "unknown", "label": "No estimate", "delta_pct": 0.0}
        delta = (asking_price - estimate) / estimate
        rating, label = DEAL_OVER
        for threshold, r, l in DEAL_BANDS:
            if delta <= threshold:
                rating, label = r, l
                break
        return {
            "rating": rating,
            "label": label,
            "delta_pct": round(delta * 100, 1),
            "delta_gbp": round(asking_price - estimate, 2),
        }

    # ---------- 3. why this price (counterfactual attribution) ----------
    def explain(self, row: dict[str, Any], top_n: int = 6) -> list[dict[str, Any]]:
        """Estimate each attribute's GBP impact versus a baseline car.

        For each feature we swap the user's value for the corpus baseline
        (median for numbers, mode for categories) and measure how much the
        prediction moves. A positive number means this attribute makes the
        car worth more than the average car in the data.
        """
        if not self.baseline_car:
            return []
        base_pred = self._raw_point({**row, **self.baseline_car})
        contributions = []
        explain_features = ["brand", "mileage", "age", "fuelType", "transmission", "engineSize"]
        for feat in explain_features:
            if feat not in row:
                continue
            # car identical to the user's, except this one feature reset to baseline
            cf = dict(row)
            cf[feat] = self.baseline_car[feat]
            cf_pred = self._raw_point(cf)
            delta = self._adjust(self._raw_point(row)) - self._adjust(cf_pred)
            contributions.append({
                "feature": feat,
                "label": _pretty_feature(feat, row[feat]),
                "impact_gbp": round(delta, 2),
            })
        contributions.sort(key=lambda c: abs(c["impact_gbp"]), reverse=True)
        return contributions[:top_n]

    # ---------- 4. depreciation forecast --------------------------------
    def depreciation(self, row: dict[str, Any], years: int = 5) -> list[dict[str, Any]]:
        """Project the car's value forward, ageing it and adding average miles."""
        series = []
        start_mileage = float(row["mileage"])
        start_age = float(row["age"])
        for t in range(0, years + 1):
            future = dict(row)
            future["age"] = start_age + t
            future["mileage"] = start_mileage + t * AVG_MILES_PER_YEAR
            value = self._adjust(self._raw_point(future))
            series.append({
                "year_offset": t,
                "calendar_year": FORECAST_BASE_YEAR + t,
                "age": int(start_age + t),
                "mileage": int(start_mileage + t * AVG_MILES_PER_YEAR),
                "value": round(value, 2),
            })
        # express each point as % of today's value for the chart
        today = series[0]["value"] or 1.0
        for p in series:
            p["pct_of_today"] = round(100 * p["value"] / today, 1)
        return series

    # ---------- 5. comparable cars --------------------------------------
    def comparables(self, row: dict[str, Any], k: int = 5) -> list[dict[str, Any]]:
        """Nearest neighbours from the corpus (same brand, closest spec)."""
        df = self.corpus
        same = df[df["brand"] == row["brand"]]
        if "model" in row:
            same_model = same[same["model"] == row["model"]]
            if len(same_model) >= k:
                same = same_model
        if same.empty:
            same = df
        # scale numeric distance so mileage doesn't dominate age/engine
        feats = ["age", "mileage", "engineSize"]
        sub = same[feats].astype(float)
        scale = sub.std().replace(0, 1.0)
        target = np.array([float(row[f]) for f in feats])
        dist = (((sub - target) / scale) ** 2).sum(axis=1) ** 0.5
        nearest = same.assign(_dist=dist).nsmallest(k, "_dist")
        out = []
        for _, r in nearest.iterrows():
            out.append({
                "brand": r["brand"],
                "model": r["model"],
                "year": REFERENCE_YEAR - int(r["age"]),
                "mileage": int(r["mileage"]),
                "transmission": r["transmission"],
                "fuelType": r["fuelType"],
                "engineSize": float(r["engineSize"]),
                "price": round(self._adjust(float(r["price"])), 2),
            })
        return out

    # ---------- orchestration -------------------------------------------
    def full_report(self, row: dict[str, Any], asking_price: float | None = None) -> dict[str, Any]:
        """One call that returns everything the frontend needs."""
        prices = self.predict(row)
        report: dict[str, Any] = {
            "currency": "GBP",
            "estimate": prices["point"],
            "range_low": prices.get("low"),
            "range_high": prices.get("high"),
            "market_factor": self.market_factor,
            "explanation": self.explain(row),
            "depreciation": self.depreciation(row),
            "comparables": self.comparables(row),
        }
        if asking_price is not None:
            report["deal"] = self.deal_rating(asking_price, prices["point"])
        return report


def _pretty_feature(feature: str, value: Any) -> str:
    """Human-readable label for the 'why this price' chart."""
    if feature == "brand":
        return f"{value} badge"
    if feature == "mileage":
        return f"{int(float(value)):,} miles"
    if feature == "age":
        return f"{int(float(value))} years old"
    if feature == "fuelType":
        return f"{value} fuel"
    if feature == "transmission":
        return f"{value} gearbox"
    if feature == "engineSize":
        return f"{value}L engine"
    return str(value)

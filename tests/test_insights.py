"""Tests for the ValuationEngine and the enriched /predict endpoint.

These cover the features that turn the artefact from a price predictor into a
buying assistant: prediction intervals, the market adjustment, the CarGurus-
style deal rating, the why-this-price attribution, the depreciation forecast
and the comparable-car lookup.

Run:
    pytest tests/test_insights.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.app import create_app, _build_engine

BMW = {
    "brand": "BMW", "model": "3 Series", "transmission": "Automatic",
    "fuelType": "Diesel", "mileage": 28000.0, "engineSize": 2.0, "age": 6,
}


@pytest.fixture(scope="module")
def engine():
    eng = _build_engine()
    if eng is None:
        pytest.skip("model artifacts not present; run `python -m src.models.train`")
    return eng


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


# ---------- prediction interval (TC) ------------------------------------

def test_predict_returns_point_and_interval(engine):
    out = engine.predict(BMW)
    assert "point" in out and out["point"] > 0
    assert "low" in out and "high" in out


def test_interval_brackets_point(engine):
    out = engine.predict(BMW)
    assert out["low"] <= out["point"] <= out["high"]


def test_interval_has_positive_width(engine):
    out = engine.predict(BMW)
    assert out["high"] > out["low"]


# ---------- market adjustment -------------------------------------------

def test_market_factor_applied(engine):
    raw = engine._raw_point(BMW)
    adjusted = engine.predict(BMW)["point"]
    # estimate should equal raw * market_factor (within rounding)
    assert abs(adjusted - raw * engine.market_factor) < 1.0


def test_market_factor_above_one(engine):
    # the documented 2020->2026 adjustment lifts prices
    assert engine.market_factor >= 1.0


# ---------- deal rating --------------------------------------------------

def test_deal_great_when_far_below(engine):
    d = engine.deal_rating(asking_price=10000, estimate=20000)
    assert d["rating"] == "great"


def test_deal_overpriced_when_far_above(engine):
    d = engine.deal_rating(asking_price=30000, estimate=20000)
    assert d["rating"] == "overpriced"


def test_deal_fair_when_close(engine):
    d = engine.deal_rating(asking_price=20100, estimate=20000)
    assert d["rating"] == "fair"


def test_deal_delta_sign(engine):
    over = engine.deal_rating(25000, 20000)
    under = engine.deal_rating(18000, 20000)
    assert over["delta_gbp"] > 0 and under["delta_gbp"] < 0


# ---------- why-this-price attribution ----------------------------------

def test_explain_returns_contributions(engine):
    items = engine.explain(BMW)
    assert len(items) >= 4
    assert all("impact_gbp" in i and "label" in i for i in items)


def test_high_mileage_reduces_value(engine):
    # a high-mileage car should have a negative mileage contribution vs baseline
    high = dict(BMW, mileage=120000.0)
    items = {i["feature"]: i["impact_gbp"] for i in engine.explain(high)}
    assert items.get("mileage", 0) < 0


# ---------- depreciation forecast ---------------------------------------

def test_depreciation_length(engine):
    series = engine.depreciation(BMW, years=5)
    assert len(series) == 6  # today + 5 years


def test_depreciation_decreases_over_time(engine):
    series = engine.depreciation(BMW, years=5)
    values = [p["value"] for p in series]
    # value at year 5 should be below value today
    assert values[-1] < values[0]


def test_depreciation_pct_of_today(engine):
    series = engine.depreciation(BMW, years=5)
    assert series[0]["pct_of_today"] == 100.0


# ---------- comparable cars ---------------------------------------------

def test_comparables_count(engine):
    comps = engine.comparables(BMW, k=5)
    assert len(comps) == 5


def test_comparables_same_brand(engine):
    comps = engine.comparables(BMW, k=5)
    assert all(c["brand"] == "BMW" for c in comps)


def test_comparables_have_prices(engine):
    comps = engine.comparables(BMW, k=5)
    assert all(c["price"] > 0 for c in comps)


# ---------- API integration ---------------------------------------------

def _payload(**extra):
    base = {
        "brand": "BMW", "model": "3 Series", "year": 2019, "mileage": 28000,
        "transmission": "Automatic", "fuelType": "Diesel", "engineSize": 2.0,
    }
    base.update(extra)
    return base


def test_api_predict_full_report(client):
    r = client.post("/predict", json=_payload())
    assert r.status_code == 200
    body = r.get_json()
    for key in ("estimate", "range_low", "range_high", "explanation",
                "depreciation", "comparables", "predicted_price"):
        assert key in body


def test_api_predict_with_asking_price_returns_deal(client):
    r = client.post("/predict", json=_payload(askingPrice=24000))
    body = r.get_json()
    assert "deal" in body and body["deal"]["rating"] in {
        "great", "good", "fair", "high", "overpriced",
    }


def test_api_predict_without_asking_price_has_no_deal(client):
    r = client.post("/predict", json=_payload())
    assert "deal" not in r.get_json()


def test_api_health_reports_features(client):
    body = client.get("/health").get_json()
    assert body["features"]["interval"] is True
    assert body["features"]["comparables"] is True
    assert body["features"]["market_factor"] >= 1.0


def test_api_backward_compatible_predicted_price(client):
    body = client.post("/predict", json=_payload()).get_json()
    assert body["predicted_price"] == body["estimate"]

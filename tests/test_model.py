"""Tests for the trained XGBoost model (best_model.pkl).

Run:
    pytest tests/test_model.py -v
"""
import joblib
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "src" / "models" / "best_model.pkl"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pipeline():
    if not MODEL_PATH.exists():
        pytest.skip("best_model.pkl not found — run train first")
    return joblib.load(MODEL_PATH)


def _make_input(**overrides) -> pd.DataFrame:
    defaults = {
        "brand": "BMW",
        "model": "3 Series",
        "year": 2019,
        "mileage": 28_000,
        "transmission": "Automatic",
        "fuelType": "Diesel",
        "engineSize": 2.0,
        "age": 2025 - 2019,
    }
    defaults.update(overrides)
    return pd.DataFrame([defaults])


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------

def test_model_loads(pipeline):
    assert pipeline is not None


def test_predict_returns_scalar(pipeline):
    df = _make_input()
    pred = pipeline.predict(df)
    assert len(pred) == 1


def test_predict_positive_price(pipeline):
    df = _make_input()
    price = pipeline.predict(df)[0]
    assert price > 0, f"Negative price predicted: {price}"


def test_predict_plausible_range(pipeline):
    """BMW 3 Series 2019 should be £10k–£40k."""
    df = _make_input()
    price = pipeline.predict(df)[0]
    assert 10_000 < price < 40_000, f"Implausible price: £{price:,.0f}"


# ---------------------------------------------------------------------------
# Sensitivity tests (monotonic relationships)
# ---------------------------------------------------------------------------

def test_higher_mileage_lowers_price(pipeline):
    low = pipeline.predict(_make_input(mileage=10_000))[0]
    high = pipeline.predict(_make_input(mileage=100_000))[0]
    assert low > high, "Higher mileage should predict a lower price"


def test_newer_car_costs_more(pipeline):
    old = pipeline.predict(_make_input(year=2012, age=13))[0]
    new = pipeline.predict(_make_input(year=2021, age=4))[0]
    assert new > old, "Newer car should predict a higher price"


# ---------------------------------------------------------------------------
# Edge cases — unknown-but-valid inputs
# ---------------------------------------------------------------------------

def test_predict_minimum_mileage(pipeline):
    df = _make_input(mileage=0)
    pred = pipeline.predict(df)[0]
    assert pred > 0


def test_predict_high_mileage(pipeline):
    df = _make_input(mileage=300_000)
    pred = pipeline.predict(df)[0]
    assert pred > 0


def test_predict_all_brands(pipeline):
    """Model should return a positive prediction for every brand in vocab."""
    brands_models = [
        ("Audi", "A4"), ("BMW", "3 Series"), ("Ford", "Focus"),
        ("Hyundai", "Tucson"), ("Mercedes", "C Class"),
        ("Skoda", "Octavia"), ("Toyota", "Corolla"),
        ("Vauxhall", "Astra"), ("Volkswagen", "Golf"),
    ]
    for brand, model in brands_models:
        df = _make_input(brand=brand, model=model)
        price = pipeline.predict(df)[0]
        assert price > 0, f"{brand} {model} gave non-positive price {price}"


def test_predict_batch(pipeline):
    """Model should handle a batch DataFrame without errors."""
    rows = [
        _make_input(brand="Ford", model="Fiesta", year=2017,
                    mileage=45_000, fuelType="Petrol", age=8),
        _make_input(brand="Volkswagen", model="Golf", year=2020,
                    mileage=15_000, fuelType="Petrol", age=5),
        _make_input(brand="Toyota", model="Prius", year=2018,
                    mileage=60_000, fuelType="Hybrid", age=7),
    ]
    df = pd.concat(rows, ignore_index=True)
    preds = pipeline.predict(df)
    assert len(preds) == 3
    assert all(p > 0 for p in preds)

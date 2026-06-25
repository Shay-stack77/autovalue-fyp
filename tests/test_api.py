"""Integration tests for the Flask REST API.

Run:
    pytest tests/test_api.py -v
"""
import json
import pytest
from pathlib import Path

# We import create_app so pytest-flask can spin up the app without a
# running server (uses the Flask test client).
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.app import create_app


# ---------------------------------------------------------------------------
# App fixture (pytest-flask)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_health_json_shape(client):
    r = client.get("/health")
    data = r.get_json()
    assert "status" in data
    assert "model_loaded" in data
    assert data["status"] == "ok"


def test_health_model_loaded(client):
    data = client.get("/health").get_json()
    assert data["model_loaded"] is True, "Model should be loaded in tests"


# ---------------------------------------------------------------------------
# /vocab
# ---------------------------------------------------------------------------

def test_vocab_returns_200(client):
    assert client.get("/vocab").status_code == 200


def test_vocab_has_required_keys(client):
    data = client.get("/vocab").get_json()
    for key in ("brands", "transmissions", "fuelTypes", "models_by_brand"):
        assert key in data, f"Missing key: {key}"


def test_vocab_brands_non_empty(client):
    data = client.get("/vocab").get_json()
    assert len(data["brands"]) >= 9


def test_vocab_models_by_brand_non_empty(client):
    data = client.get("/vocab").get_json()
    for brand, models in data["models_by_brand"].items():
        assert len(models) > 0, f"No models for brand: {brand}"


# ---------------------------------------------------------------------------
# /predict — happy path
# ---------------------------------------------------------------------------

VALID_PAYLOAD = {
    "brand": "BMW",
    "model": "3 Series",
    "year": "2019",
    "mileage": "28000",
    "transmission": "Automatic",
    "fuelType": "Diesel",
    "engineSize": "2.0",
}


def test_predict_returns_200(client):
    r = client.post("/predict",
                    data=json.dumps(VALID_PAYLOAD),
                    content_type="application/json")
    assert r.status_code == 200


def test_predict_returns_predicted_price(client):
    r = client.post("/predict",
                    data=json.dumps(VALID_PAYLOAD),
                    content_type="application/json")
    data = r.get_json()
    assert "predicted_price" in data
    assert "currency" in data
    assert data["currency"] == "GBP"


def test_predict_price_is_numeric(client):
    r = client.post("/predict",
                    data=json.dumps(VALID_PAYLOAD),
                    content_type="application/json")
    price = r.get_json()["predicted_price"]
    assert isinstance(price, (int, float))
    assert price > 0


def test_predict_bmw_3series_plausible(client):
    r = client.post("/predict",
                    data=json.dumps(VALID_PAYLOAD),
                    content_type="application/json")
    price = r.get_json()["predicted_price"]
    assert 10_000 < price < 45_000, f"Implausible price £{price:,.0f}"


# ---------------------------------------------------------------------------
# /predict — edge cases
# ---------------------------------------------------------------------------

def test_predict_missing_field_returns_400(client):
    bad = dict(VALID_PAYLOAD)
    del bad["brand"]
    r = client.post("/predict",
                    data=json.dumps(bad),
                    content_type="application/json")
    assert r.status_code == 400


def test_predict_wrong_content_type_returns_400(client):
    r = client.post("/predict",
                    data="not json",
                    content_type="text/plain")
    assert r.status_code == 400


def test_predict_ford_fiesta(client):
    payload = {
        "brand": "Ford", "model": "Fiesta", "year": "2017",
        "mileage": "45000", "transmission": "Manual",
        "fuelType": "Petrol", "engineSize": "1.0",
    }
    r = client.post("/predict",
                    data=json.dumps(payload),
                    content_type="application/json")
    assert r.status_code == 200
    price = r.get_json()["predicted_price"]
    assert 3_000 < price < 18_000, f"Ford Fiesta price implausible: £{price:,.0f}"


def test_predict_electric_car(client):
    """Electric cars — known to model via fuelType OHE."""
    payload = {
        "brand": "Hyundai", "model": "Ioniq", "year": "2020",
        "mileage": "20000", "transmission": "Automatic",
        "fuelType": "Electric", "engineSize": "0.0",
    }
    r = client.post("/predict",
                    data=json.dumps(payload),
                    content_type="application/json")
    # May hit OHE unknown for engine size 0.0 — still should not crash
    assert r.status_code in (200, 400)


# ---------------------------------------------------------------------------
# Frontend static files
# ---------------------------------------------------------------------------

def test_root_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"<!DOCTYPE html>" in r.data or b"html" in r.data.lower()

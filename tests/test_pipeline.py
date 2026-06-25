"""Tests for the preprocessing pipeline.

Run:
    pytest tests/test_pipeline.py -v
"""
import pandas as pd
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cleaned_df():
    path = PROJECT_ROOT / "data" / "cleaned" / "listings.csv"
    if not path.exists():
        pytest.skip("Cleaned dataset not found — run preprocess first")
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = {"model", "year", "price", "transmission",
                    "mileage", "fuelType", "engineSize", "brand", "age"}


def test_cleaned_has_expected_columns(cleaned_df):
    missing = EXPECTED_COLUMNS - set(cleaned_df.columns)
    assert not missing, f"Missing columns: {missing}"


def test_no_nulls_in_required_fields(cleaned_df):
    required = ["brand", "model", "year", "price",
                "transmission", "mileage", "fuelType", "engineSize"]
    null_counts = cleaned_df[required].isnull().sum()
    assert null_counts.sum() == 0, f"Nulls found:\n{null_counts[null_counts > 0]}"


def test_price_within_range(cleaned_df):
    assert (cleaned_df["price"] > 100).all(), "Prices ≤ 100 found"
    assert (cleaned_df["price"] < 500_000).all(), "Unrealistic price outlier found"


def test_year_within_range(cleaned_df):
    assert cleaned_df["year"].between(1990, 2025).all()


def test_mileage_non_negative(cleaned_df):
    assert (cleaned_df["mileage"] >= 0).all()


def test_engine_size_sensible(cleaned_df):
    assert cleaned_df["engineSize"].between(0.5, 8.0).all()


def test_age_column_correct(cleaned_df):
    expected_age = 2025 - cleaned_df["year"]
    assert (cleaned_df["age"] == expected_age).all()


def test_no_duplicate_rows(cleaned_df):
    """Exact-duplicate listings (same spec + price) should be <0.5 % of corpus.
    A small number of identical entries is realistic in real market data."""
    subset = ["brand", "model", "year", "price", "mileage",
              "transmission", "fuelType", "engineSize"]
    dups = cleaned_df.duplicated(subset=subset).sum()
    pct = dups / len(cleaned_df) * 100
    assert pct < 0.5, f"{dups} duplicate rows found ({pct:.2f}% — exceeds 0.5% threshold)"


def test_known_brands_present(cleaned_df):
    expected = {"Audi", "BMW", "Ford", "Hyundai",
                "Mercedes", "Skoda", "Toyota", "Vauxhall", "Volkswagen"}
    actual = set(cleaned_df["brand"].unique())
    assert expected == actual


def test_row_count_reasonable(cleaned_df):
    """After cleaning we expect ≥ 80 k rows from the 99 k raw rows."""
    assert len(cleaned_df) >= 80_000, f"Only {len(cleaned_df):,} rows after cleaning"

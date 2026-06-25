"""Data cleaning and feature engineering for the UK used-cars dataset.

Expected raw columns (per the 100,000 UK Used Car dataset on Kaggle):
    model, year, price, transmission, mileage, fuelType, tax, mpg, engineSize

A `brand` column is appended when multiple brand CSVs are merged.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
CLEANED_DIR = Path(__file__).resolve().parents[2] / "data" / "cleaned"
CLEANED_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_COLS = {"model", "year", "price", "transmission",
                 "mileage", "fuelType", "engineSize"}

# Brands shipped in the dataset (filename stem -> display brand)
BRAND_FILES = {
    "audi": "Audi", "bmw": "BMW", "ford": "Ford", "hyundi": "Hyundai",
    "merc": "Mercedes", "skoda": "Skoda", "toyota": "Toyota",
    "vauxhall": "Vauxhall", "vw": "Volkswagen",
}


def load_raw(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Load every recognised brand CSV in `raw_dir` and concatenate them."""
    frames = []
    for stem, brand in BRAND_FILES.items():
        path = raw_dir / f"{stem}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        df["brand"] = brand
        frames.append(df)

    if not frames:
        raise FileNotFoundError(
            f"No brand CSVs found in {raw_dir}. Expected files like audi.csv, bmw.csv, ..."
        )

    combined = pd.concat(frames, ignore_index=True)
    missing = EXPECTED_COLS - set(combined.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {missing}")
    return combined


def _strip_whitespace(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    return df


def _remove_outliers_iqr(df: pd.DataFrame, col: str, k: float = 1.5) -> pd.DataFrame:
    q1, q3 = df[col].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - k * iqr, q3 + k * iqr
    return df[(df[col] >= lower) & (df[col] <= upper)].copy()


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the merged dataset:
       - strip whitespace
       - drop rows missing a target or required feature
       - drop duplicates
       - remove outliers from price + mileage (IQR rule)
       - engineer `age` from `year`
       - clip implausible engineSize values
    """
    df = _strip_whitespace(df.copy())

    # Drop rows with missing critical fields
    required = ["price", "year", "mileage", "model", "brand",
                "transmission", "fuelType", "engineSize"]
    df = df.dropna(subset=required)

    # Drop duplicates
    df = df.drop_duplicates()

    # Remove implausible / outlier rows
    df = df[df["price"] > 100]                       # rule out £0 / £1 listings
    df = df[df["year"].between(1990, 2025)]
    df = df[df["mileage"] >= 0]
    df = df[df["engineSize"].between(0.5, 8.0)]
    df = _remove_outliers_iqr(df, "price")
    df = _remove_outliers_iqr(df, "mileage")

    # Feature engineering
    df["age"] = 2025 - df["year"].astype(int)
    df = df[df["age"] >= 0]

    return df.reset_index(drop=True)


def save_cleaned(df: pd.DataFrame, name: str = "listings.csv") -> Path:
    out = CLEANED_DIR / name
    df.to_csv(out, index=False)
    return out


def run() -> Path:
    raw = load_raw()
    print(f"[preprocess] loaded {len(raw):,} raw rows from {RAW_DIR}")
    cleaned = clean(raw)
    print(f"[preprocess] cleaned -> {len(cleaned):,} rows "
          f"({len(raw) - len(cleaned):,} dropped)")
    out = save_cleaned(cleaned)
    print(f"[preprocess] wrote {out}")
    return out


if __name__ == "__main__":
    run()

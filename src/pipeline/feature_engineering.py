"""Build the scikit-learn ColumnTransformer used for both training and
prediction. Keeping this in a single module guarantees train-time and
serve-time feature engineering match exactly."""
from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC_FEATURES = ["mileage", "engineSize", "age"]
CATEGORICAL_FEATURES = ["brand", "model", "transmission", "fuelType"]
TARGET = "price"
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat",
             OneHotEncoder(handle_unknown="ignore", sparse_output=False),
             CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )


def features_target(df: pd.DataFrame):
    return df[ALL_FEATURES].copy(), df[TARGET].copy()

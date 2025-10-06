import logging
from pathlib import Path

import joblib
import pandas as pd
import xgboost as xgb

log = logging.getLogger(__name__)


def train_model(features_path: str, model_output_path: str):
    """
    Trains an XGBoost model on the engineered features and saves it.

    Args:
        features_path: Path to the Parquet file with engineered features.
        model_output_path: Path to save the trained model file.
    """
    log.info(f"Loading features from {features_path}")
    if not Path(features_path).exists():
        log.error(f"Features file not found at {features_path}")
        raise FileNotFoundError(f"Features file not found at {features_path}")

    df = pd.read_parquet(features_path)
    log.info(f"Loaded {len(df)} rows of data.")

    # --- Basic Feature/Target Preparation ---
    # Define the target variable: 1 if the next close is higher, 0 otherwise.
    # This is a simple example; a real target would be more sophisticated.
    df["target"] = (df.groupby("symbol")["close"].shift(-1) > df["close"]).astype(int)

    # Drop rows with NaN values (especially the last row for each symbol due to the shift)
    df.dropna(subset=["target"], inplace=True)

    # Define features (X) and target (y)
    # Exclude non-feature columns
    feature_cols = [
        col
        for col in df.columns
        if col
        not in [
            "symbol",
            "timestamp",
            "target",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]
    X = df[feature_cols]
    y = df["target"]

    if X.empty:
        log.error("No features available for training after processing. Aborting.")
        return

    log.info(f"Training model on {len(X)} samples with {len(feature_cols)} features.")

    # --- Model Training ---
    # Initialize and train the XGBoost Classifier
    model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        use_label_encoder=False,
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )

    model.fit(X, y)
    log.info("Model training completed.")

    # --- Save the Model ---
    output_path = Path(model_output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    log.info(f"Model saved successfully to {output_path}")


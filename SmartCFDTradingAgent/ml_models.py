from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - optional dependency
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    import joblib
except Exception:  # pragma: no cover
    GradientBoostingClassifier = None
    Pipeline = None
    StandardScaler = None
    joblib = None


class PriceDirectionModel:
    """Simple wrapper around a GradientBoostingClassifier.

    The model predicts probabilities for three classes: Sell, Hold and Buy
    given a series of closing prices.  Features are based on recent returns.
    """

    def __init__(self, model: Optional[Pipeline] = None) -> None:
        self.model = model

    # ---------------------------- feature helpers ----------------------------
    @staticmethod
    def _make_features(close: pd.Series) -> pd.DataFrame:
        df = pd.DataFrame({"close": close})
        df["ret1"] = df["close"].pct_change()
        df["ret5"] = df["close"].pct_change(5)
        df["ret10"] = df["close"].pct_change(10)
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma20_ret"] = df["ma20"].pct_change()
        features = df[["ret1", "ret5", "ret10", "ma20_ret"]].dropna()
        return features

    @staticmethod
    def _make_labels(close: pd.Series, threshold: float = 0.001) -> pd.Series:
        future_ret = close.pct_change().shift(-1)
        lbl = pd.Series("Hold", index=future_ret.index)
        lbl[future_ret > threshold] = "Buy"
        lbl[future_ret < -threshold] = "Sell"
        return lbl[:-1]  # last NaN removed

    # -------------------------------------------------------------------------
    def fit(self, price_df: pd.DataFrame) -> None:
        """Train the model on a DataFrame containing at least a 'Close' column."""
        if GradientBoostingClassifier is None:
            raise RuntimeError("scikit-learn is required for training")

        close = price_df["Close"] if "Close" in price_df.columns else price_df.squeeze()
        features = self._make_features(close)
        labels = self._make_labels(close).loc[features.index]
        y = labels.map({"Sell": 0, "Hold": 1, "Buy": 2}).to_numpy()
        X = features.to_numpy()
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("gb", GradientBoostingClassifier()),
        ])
        pipe.fit(X, y)
        self.model = pipe

    # ------------------------------ prediction ------------------------------
    def predict_proba(self, close: pd.Series) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model not trained/loaded")
        features = self._make_features(close).tail(1).to_numpy()
        return self.model.predict_proba(features)

    def predict_signal(self, close: pd.Series) -> tuple[str, float]:
        proba = self.predict_proba(close)[0]
        idx = int(np.argmax(proba))
        side = ["Sell", "Hold", "Buy"][idx]
        return side, float(proba[idx])

    # ------------------------------ persistence ------------------------------
    def save(self, path: str | Path) -> None:
        if joblib is None:
            raise RuntimeError("joblib is required to save models")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path)

    @classmethod
    def load(cls, path: str | Path) -> "PriceDirectionModel":
        if joblib is None:
            raise RuntimeError("joblib is required to load models")
        model = joblib.load(path)
        return cls(model)


__all__ = ["PriceDirectionModel"]

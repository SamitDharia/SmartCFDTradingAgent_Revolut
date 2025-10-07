"""
This module contains the core logic for training, evaluating, and saving the ML model.
It is designed to be reusable by both manual training scripts and automated retraining workflows.
"""
import pandas as pd
from sklearn.model_selection import train_test_split, RandomizedSearchCV, TimeSeriesSplit
from xgboost import XGBClassifier
from sklearn.metrics import classification_report
import joblib
from alpaca.data.timeframe import TimeFrame
from smartcfd.data_loader import fetch_data
from smartcfd.indicators import create_features
from smartcfd.config import load_config
import numpy as np
import os
from pathlib import Path
import matplotlib.pyplot as plt

# --- Default Configuration ---
config = load_config()
DEFAULT_SYMBOL = config.watch_list.split(',')[0].strip()
DEFAULT_START_DATE = "2022-01-01"
DEFAULT_END_DATE = "2024-01-01"
DEFAULT_TIMEFRAME = TimeFrame.Hour
DEFAULT_MODEL_PATH = "models/model.joblib"
REPORTS_DIR = "reports"

def create_target(df: pd.DataFrame, period: int = 1) -> pd.Series:
    """
    Create the target variable. 1 for price increase, 0 for price decrease.
    """
    return (df['close'].shift(-period) > df['close']).astype(int)

def train_and_evaluate_model(
    symbol: str = DEFAULT_SYMBOL,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    timeframe: TimeFrame = DEFAULT_TIMEFRAME,
    model_output_path: str = DEFAULT_MODEL_PATH
):
    """
    Fetches data, creates features, trains an XGBoost model with hyperparameter tuning,
    evaluates it, and saves it to disk.
    """
    print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
    df = fetch_data(symbol, timeframe, start_date, end_date)
    
    if df.empty:
        print("No data fetched. Exiting.")
        return

    if isinstance(df.index, pd.MultiIndex):
        df.index = df.index.get_level_values('timestamp')

    print("Creating features...")
    df_features = create_features(df)

    print("Creating target variable...")
    df_features['target'] = create_target(df_features)

    df_features.dropna(inplace=True)

    features = [col for col in df_features.columns if col not in ['open', 'high', 'low', 'close', 'volume', 'trade_count', 'vwap', 'target']]
    X = df_features[features]
    y = df_features['target']

    if len(X) == 0:
        print("Not enough data to train after processing. Exiting.")
        return

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

    print(f"Training model on {len(X_train)} samples...")
    
    print("Performing hyperparameter tuning for XGBoost...")
    param_dist = {
        'n_estimators': [int(x) for x in np.linspace(start=100, stop=1000, num=10)],
        'learning_rate': [0.01, 0.05, 0.1, 0.2],
        'max_depth': [3, 4, 5, 6, 7, 8],
        'colsample_bytree': [0.3, 0.5, 0.7, 1.0],
        'subsample': [0.6, 0.8, 1.0],
        'gamma': [0, 0.1, 0.2, 0.3]
    }

    xgb = XGBClassifier(random_state=42, use_label_encoder=False, eval_metric='logloss')

    # Use TimeSeriesSplit for cross-validation
    tscv = TimeSeriesSplit(n_splits=3)

    random_search = RandomizedSearchCV(
        estimator=xgb,
        param_distributions=param_dist,
        n_iter=30,
        cv=tscv,
        verbose=2,
        random_state=42,
        n_jobs=-1
    )

    random_search.fit(X_train, y_train)

    print("Best parameters found: ", random_search.best_params_)
    
    model = random_search.best_estimator_

    print("Evaluating best XGBoost model found...")
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))

    # --- Feature Importance Analysis ---
    print("Analyzing feature importances...")
    feature_importances = pd.DataFrame({
        'feature': X_train.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    # Ensure reports directory exists
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    # Save feature importances to CSV
    importance_csv_path = Path(REPORTS_DIR) / "feature_importances.csv"
    feature_importances.to_csv(importance_csv_path, index=False)
    print(f"Feature importances saved to {importance_csv_path}")

    # Plot and save feature importances
    plt.figure(figsize=(12, 8))
    plt.title('Feature Importances')
    plt.barh(feature_importances['feature'], feature_importances['importance'])
    plt.xlabel('Importance')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    
    importance_plot_path = Path(REPORTS_DIR) / "feature_importances.png"
    plt.savefig(importance_plot_path)
    print(f"Feature importance plot saved to {importance_plot_path}")
    plt.close()

    # Ensure the directory exists
    output_dir = Path(model_output_path).parent
    os.makedirs(output_dir, exist_ok=True)

    print(f"Saving model to {model_output_path}...")
    joblib.dump(model, model_output_path)
    print("Model saved successfully.")

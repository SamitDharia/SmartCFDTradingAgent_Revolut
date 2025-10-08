"""
This module contains the core logic for training, evaluating, and saving the ML model.
It is designed to be reusable by both manual training scripts and automated retraining workflows.
"""
import pandas as pd
from sklearn.model_selection import train_test_split, RandomizedSearchCV, TimeSeriesSplit
from xgboost import XGBClassifier
from sklearn.metrics import classification_report
import joblib
from smartcfd.data_loader import DataLoader
from .indicators import (
    atr, rsi, macd, bollinger_bands, adx,
    stochastic_oscillator, volume_profile, price_rate_of_change
)
from smartcfd.config import load_config_from_file
import numpy as np
import os
from pathlib import Path
import matplotlib.pyplot as plt

# --- Default Configuration ---
app_cfg, _, _ = load_config_from_file()
DEFAULT_SYMBOL = app_cfg.watch_list.split(',')[0].strip()
DEFAULT_START_DATE = "2022-01-01"
DEFAULT_END_DATE = "2024-01-01"
DEFAULT_TIMEFRAME = app_cfg.trade_interval
DEFAULT_MODEL_PATH = "models/model.joblib"
REPORTS_DIR = "reports"

def create_target(df: pd.DataFrame, period: int = 5) -> pd.Series:
    """
    Creates the target variable for classification.
    - 1: Buy (price is expected to increase significantly)
    - 2: Sell (price is expected to decrease significantly)
    - 0: Hold (price is not expected to move significantly)
    """
    future_returns = df['close'].pct_change(periods=period).shift(-period)
    
    # Define thresholds for buy/sell signals
    # These should be tuned based on asset volatility and strategy goals
    buy_threshold = 0.01  # e.g., 1% increase
    sell_threshold = -0.01 # e.g., 1% decrease

    conditions = [
        future_returns > buy_threshold,
        future_returns < sell_threshold
    ]
    choices = [1, 2] # 1 for Buy, 2 for Sell
    
    return np.select(conditions, choices, default=0) # 0 for Hold


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a rich set of features for the model from historical data.
    """
    if df.empty:
        return pd.DataFrame()

    df.columns = [x.lower() for x in df.columns]
    features = pd.DataFrame(index=df.index)

    # Basic returns
    features['feature_return_1m'] = df['close'].pct_change(1)
    features['feature_return_5m'] = df['close'].pct_change(5)
    features['feature_return_15m'] = df['close'].pct_change(15)

    # Volatility
    features['feature_volatility_5m'] = features['feature_return_1m'].rolling(5).std()
    features['feature_volatility_15m'] = features['feature_return_1m'].rolling(15).std()

    # Technical Indicators
    bollinger = bollinger_bands(df['close'])
    features['feature_bband_mavg'] = bollinger['BBM_20_2.0']
    features['feature_bband_hband'] = bollinger['BBH_20_2.0']
    features['feature_bband_lband'] = bollinger['BBL_20_2.0']

    macd_df = macd(df['close'])
    features['feature_macd'] = macd_df['MACD_12_26_9']
    features['feature_macd_signal'] = macd_df['MACDs_12_26_9']
    features['feature_macd_diff'] = macd_df['MACDh_12_26_9']

    stoch = stochastic_oscillator(df['high'], df['low'], df['close'])
    features['feature_stoch_k'] = stoch['STOCHk_14_3_3']
    features['feature_stoch_d'] = stoch['STOCHd_14_3_3']

    # Time-based features
    features['feature_day_of_week'] = df.index.dayofweek
    features['feature_hour_of_day'] = df.index.hour
    features['feature_minute_of_hour'] = df.index.minute

    return features.dropna()


def train_and_evaluate_model(
    symbol: str = DEFAULT_SYMBOL,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    timeframe_str: str = DEFAULT_TIMEFRAME,
    model_output_path: str = DEFAULT_MODEL_PATH
):
    """
    Fetches data, creates features, trains an XGBoost model with hyperparameter tuning,
    evaluates it, and saves it to disk.
    """
    print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
    loader = DataLoader()
    df = loader.fetch_historical_range(symbol, start_date, end_date, timeframe_str)
    
    if df.empty:
        print("No data fetched. Exiting.")
        return

    if isinstance(df.index, pd.MultiIndex):
        df.index = df.index.get_level_values('timestamp')

    print("Creating features...")
    df_features = create_features(df)

    print("Creating target variable...")
    target = create_target(df)
    target = pd.Series(target, index=df.index) # Ensure target is a Series with the correct index

    # Align features and target by index
    aligned_index = df_features.index.intersection(target.index)
    df_features = df_features.loc[aligned_index]
    df_features['target'] = target.loc[aligned_index]

    df_features.dropna(inplace=True)

    # Align dataframes by index
    df = df.loc[df_features.index]
    
    # Ensure all feature columns are included
    features = [col for col in df_features.columns if col.startswith('feature_')]
    X = df_features[features]
    y = df_features['target']

    if len(X) == 0:
        print("Not enough data to train after processing. Exiting.")
        return

    # Save feature names
    feature_names = X.columns.tolist()
    joblib.dump(feature_names, 'models/feature_names.joblib')
    print(f"Saved {len(feature_names)} feature names to models/feature_names.joblib")

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

    xgb = XGBClassifier(random_state=42, use_label_encoder=False, eval_metric='mlogloss', objective='multi:softprob', num_class=3)

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

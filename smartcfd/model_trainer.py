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
from smartcfd.features import create_features
from smartcfd.config import load_config_from_file
import numpy as np
import os
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.utils import class_weight

# --- Default Configuration ---
app_cfg, _, _, _ = load_config_from_file()
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


    # feature engineering now imported from smartcfd.features


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
    app_cfg, _, alpaca_cfg = load_config_from_file()
    api_base = "https://paper-api.alpaca.markets" if app_cfg.alpaca_env == "paper" else "https://api.alpaca.markets"
    loader = DataLoader(
        api_key=alpaca_cfg.api_key,
        secret_key=alpaca_cfg.secret_key,
        api_base=api_base
    )
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

    print("--- Target Variable Distribution ---")
    print(y.value_counts(normalize=True))
    print("------------------------------------")

    if len(X) == 0:
        print("Not enough data to train after processing. Exiting.")
        return

    # Save feature names
    feature_names = X.columns.tolist()
    joblib.dump(feature_names, 'models/feature_names.joblib')
    print(f"Saved {len(feature_names)} feature names to models/feature_names.joblib")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

    print("Calculating class weights to handle imbalance...")
    # Calculate class weights
    classes = np.unique(y_train)
    weights = class_weight.compute_class_weight(class_weight='balanced', classes=classes, y=y_train)
    class_weights = dict(zip(classes, weights))
    print(f"Computed class weights: {class_weights}")

    # Create sample weights for the training data
    sample_weights = np.array([class_weights[i] for i in y_train])

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

    random_search.fit(X_train, y_train, sample_weight=sample_weights)

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

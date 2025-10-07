import sys
from pathlib import Path

# Add the project root to the Python path to allow importing from smartcfd
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from smartcfd.data_loader import fetch_data
from smartcfd.indicators import create_features
from alpaca.data.timeframe import TimeFrame

# --- Configuration ---
SYMBOL = "BTC/USD"
START_DATE = "2022-01-01"
END_DATE = "2024-01-01"
TIMEFRAME = TimeFrame.Hour
MODEL_OUTPUT_PATH = "model.joblib"

def create_target(df: pd.DataFrame, period: int = 1) -> pd.Series:
    """
    Create the target variable. 1 for price increase, 0 for price decrease.
    """
    return (df['close'].shift(-period) > df['close']).astype(int)

def main():
    """
    Main function to fetch data, train a model, and save it.
    """
    print(f"Fetching data for {SYMBOL} from {START_DATE} to {END_DATE}...")
    df = fetch_data(SYMBOL, TIMEFRAME, START_DATE, END_DATE)
    
    if df.empty:
        print("No data fetched. Exiting.")
        return

    # The Alpaca API returns a multi-index (symbol, timestamp).
    # We need to set the timestamp as the primary index for feature calculation.
    if isinstance(df.index, pd.MultiIndex):
        df.index = df.index.get_level_values('timestamp')

    print("Creating features...")
    df_features = create_features(df)

    print("Creating target variable...")
    df_features['target'] = create_target(df_features)

    # Drop rows with NaN values created by feature generation
    df_features.dropna(inplace=True)

    # Define features (X) and target (y)
    features = [col for col in df_features.columns if col not in ['open', 'high', 'low', 'close', 'volume', 'trade_count', 'vwap', 'target']]
    X = df_features[features]
    y = df_features['target']

    if len(X) == 0:
        print("Not enough data to train after processing. Exiting.")
        return

    # Split data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

    print(f"Training model on {len(X_train)} samples...")
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    print("Evaluating model...")
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))

    print(f"Saving model to {MODEL_OUTPUT_PATH}...")
    joblib.dump(model, MODEL_OUTPUT_PATH)
    print("Model saved successfully.")

if __name__ == "__main__":
    main()

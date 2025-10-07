"""
This script serves as a manual trigger for training the machine learning model.

It calls the centralized training and evaluation function from the `smartcfd.model_trainer`
module, which contains the core logic for data fetching, feature engineering,
hyperparameter tuning, and model serialization.

Running this script directly is useful for:
-   On-demand model retraining.
-   Testing changes to the feature engineering or model tuning process.
-   Generating an initial model if one does not exist.
"""
import sys
from pathlib import Path

# Add the project root to the Python path to allow importing from smartcfd
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from smartcfd.model_trainer import train_and_evaluate_model

def main():
    """
    Main function to trigger the model training and evaluation process.
    """
    print("--- Manual Model Training Trigger ---")
    train_and_evaluate_model()
    print("--- Manual Training Finished ---")

if __name__ == "__main__":
    main()


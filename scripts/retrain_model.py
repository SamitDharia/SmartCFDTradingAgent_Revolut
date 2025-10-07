"""
This script automates the process of retraining the machine learning model.

It is designed to be run periodically (e.g., weekly) to keep the model
up-to-date with the latest market data.

The script performs the following steps:
1.  Defines the paths for the current model and a backup location.
2.  If an existing model is found, it is moved to the backup location.
3.  It calculates a rolling date range for training (e.g., the last 2 years).
4.  It calls the core `train_and_evaluate_model` function with the new date range.
"""
import sys
from pathlib import Path
import os
import shutil
from datetime import datetime, timedelta

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from smartcfd.model_trainer import train_and_evaluate_model, DEFAULT_MODEL_PATH

def backup_model(model_path: str) -> None:
    """Backs up the existing model file."""
    model_p = Path(model_path)
    if model_p.exists():
        backup_dir = model_p.parent / "backup"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{model_p.stem}_{timestamp}{model_p.suffix}"
        
        print(f"Backing up existing model to {backup_path}...")
        shutil.move(str(model_p), str(backup_path))
        print("Backup complete.")

def main():
    """
    Main function to orchestrate the model retraining process.
    """
    print("--- Automated Model Retraining ---")
    
    # 1. Backup the current model
    backup_model(DEFAULT_MODEL_PATH)

    # 2. Define the new training period (e.g., last 2 years)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 2)
    
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    print(f"Starting retraining for period: {start_date_str} to {end_date_str}")

    # 3. Run the training process
    train_and_evaluate_model(
        start_date=start_date_str,
        end_date=end_date_str
    )
    
    print("--- Automated Retraining Finished ---")

if __name__ == "__main__":
    main()

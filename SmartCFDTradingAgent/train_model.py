from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from SmartCFDTradingAgent.ml_models import PriceDirectionModel
from SmartCFDTradingAgent.utils.logger import get_logger

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
STORE = ROOT / "storage"
log = get_logger()


log = get_logger()


def main() -> None:
    parser = argparse.ArgumentParser(description="Train ML model for SmartCFD signals")
    parser.add_argument("csv", help="Path to CSV file containing historical price data")
    parser.add_argument(
        "--output",
        default=str(STORE / "ml_model.pkl"),
        help="Where to store the trained model (default: storage/ml_model.pkl)",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")

    model = PriceDirectionModel()
    model.fit(df)
    model.save(args.output)
    log.info("Model saved to %s", args.output)


if __name__ == "__main__":
    main()

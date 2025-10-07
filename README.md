# SmartCFD Trading Agent

This project is an automated trading agent designed to analyze market data, generate trading signals using a machine learning model, and execute trades via the Alpaca Markets API. It is built with a modular architecture, allowing for different brokers and strategies to be integrated. The agent includes features for risk management, automated operations, and real-time monitoring.

## Key Features

- **Modular Architecture:** Pluggable `Broker` and `Strategy` components. Currently supports Alpaca for paper and live trading.
- **Machine Learning Strategy:** Uses an `XGBoost` model to generate buy/hold signals based on a wide range of technical indicators.
- **Risk Management:** A dedicated `RiskManager` enforces rules on position sizing, daily drawdown, and market volatility.
- **Volatility Circuit Breaker:** Automatically halts trading during periods of extreme market volatility to protect capital.
- **Data Integrity Checks:** Validates market data for staleness, gaps, and anomalies before use.
- **Automated Operations:** Includes scripts for automated model retraining on a rolling window.
- **Monitoring & Reporting:**
    - Generates a daily performance digest.
    - Sends email notifications for critical alerts and summaries.
    - Features a real-time web dashboard to visualize performance.
- **Scheduling:** Comes with documentation for scheduling the agent on both Windows (Task Scheduler) and Linux (cron).

## Project Status

The project is currently in **Phase 3: Production Readiness**. All core features, including the ML model, risk management, and automated operations, are complete. The current focus is on security hardening and preparing for live, real-money deployment with Alpaca.

## Getting Started

### Prerequisites
- Python 3.11+
- Docker and Docker Compose (recommended for ease of use)

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/SmartCFDTradingAgent_Revolut.git
    cd SmartCFDTradingAgent_Revolut
    ```

2.  **Environment Variables:**
    Copy the example environment file and fill in your credentials. This file is git-ignored.
    ```bash
    cp .env.example .env
    ```
    You will need to set your `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` for Alpaca, as well as any notification service credentials (e.g., for email). See `.env.example` for a full list of required variables.

3.  **Build and Run with Docker (Recommended):**
    Using Docker is the easiest way to run the agent, as it handles all dependencies.
    ```bash
    docker-compose build
    docker-compose run --rm trader
    ```
    This command runs the main trading loop once.

## Usage

The agent can be configured and run in several ways:

- **Run the Trader:**
  The primary entry point is `smartcfd/trader.py`, which is configured as the `trader` service in `docker-compose.yml`.

- **Train the Model:**
  To train the model manually, run the `train_model.py` script:
  ```bash
  docker-compose run --rm python scripts/train_model.py --symbol "BTC/USD" --interval "1h"
  ```

- **Automated Retraining:**
  The `retrain_model.py` script handles backing up the old model and retraining a new one on a rolling data window.
  ```bash
  docker-compose run --rm python scripts/retrain_model.py
  ```

- **Daily Summary:**
  Generate and send the daily performance digest.
  ```bash
  docker-compose run --rm python scripts/daily_summary.py
  ```

## Automation & Scheduling

The agent is designed for automated, unattended operation. Detailed instructions for scheduling the trading and retraining scripts are available in the `docs` folder:
- **`docs/linux-scheduling.md`**: Guide for using `cron` on Linux.
- **`docs/windows-scheduling.md`**: Guide for using `Task Scheduler` on Windows.

## Project Structure

- `smartcfd/`: Core source code for the agent.
  - `trader.py`: Main application logic.
  - `broker.py`, `alpaca.py`: Broker integrations.
  - `strategy.py`: Trading strategy logic.
  - `model_trainer.py`: Model training and evaluation.
  - `risk.py`: Risk management rules.
  - `data_loader.py`: Data fetching and integrity checks.
- `scripts/`: Standalone scripts for training, reporting, etc.
- `models/`: Default location for the trained model file (`model.joblib`).
- `configs/`: YAML configuration files for different assets.
- `tests/`: Unit and integration tests.
- `docs/`: Project documentation.

## Contributing

Contributions are welcome. Please open an issue to discuss any major changes before submitting a pull request.


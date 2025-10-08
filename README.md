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

**Version 1.0 (Stable):** The project is feature-complete and stable. All core systems, including the ML model, risk management, and automated operations, are fully functional and have been validated in a live paper-trading environment. The agent is now ready for continuous operation and monitoring.

## Getting Started

### Prerequisites
- Python 3.11+
- Docker and Docker Compose

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/SmartCFDTradingAgent_Revolut.git
    cd SmartCFDTradingAgent_Revolut
    ```

2.  **Configure Environment:**
    Create a `.env` file from the example and add your Alpaca API keys and any other required credentials.
    ```bash
    cp config.ini.example config.ini
    ```
    *Note: The project now uses `config.ini` for credentials.*

3.  **Build and Run with Docker:**
    Using Docker is the recommended way to run the agent, as it handles all dependencies and ensures a consistent environment.
    ```bash
    docker-compose up --build -d
    ```
    This command builds the Docker image and starts the agent in detached mode (running in the background).

## Usage

The agent is designed for autonomous operation. Once started, it will run continuously according to the schedule defined in its configuration.

- **View Live Logs:**
  To monitor the agent's activity in real-time, use the following command:
  ```bash
  docker-compose logs --tail 100 -f
  ```

- **Stop the Agent:**
  To stop the agent and shut down the container, run:
  ```bash
  docker-compose down
  ```

- **Manual Operations (Training, Backtesting):**
  While the agent is designed to be autonomous, you can still run manual scripts for maintenance or analysis. See the `scripts/` directory for available tools.
  ```bash
  # Example: Manually retrain the model
  docker-compose run --rm app python scripts/retrain_model.py
  ```

## Automation & Scheduling

The agent runs on an internal timer (`run_interval_seconds` in the config) and does not require external scheduling tools like `cron` or Windows Task Scheduler when run via Docker. For more advanced scheduling scenarios, see the documentation:
- **`docs/linux-scheduling.md`**
- **`docs/windows-scheduling.md`**

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

---

## ⚠️ Live Trading Warning

This trading bot is capable of executing trades with real money. Before switching to a live environment, you MUST understand and accept the risks involved.

### How to Enable Live Trading

1.  **Open the `.env` file** in the root of the project directory.
2.  **Change the `ALPACA_ENV` variable** from `paper` to `live`.
    ```
    # .env file
    # ... other variables
    ALPACA_ENV=live
    ```
3.  **Ensure your Alpaca API keys** (`APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`) are for your **live trading account**.

When you start the bot with `ALPACA_ENV=live`, you will see a critical warning message in the logs, and the bot will pause for 5 seconds. This is your final opportunity to stop the execution if you enabled live mode by mistake.

**RISK DISCLAIMER:** Trading financial markets involves substantial risk of loss and is not suitable for every investor. The creators of this software are not liable for any financial losses incurred by its use. **Use at your own risk.**


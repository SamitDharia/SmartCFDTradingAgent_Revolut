# SmartCFD Trading Agent - Project Roadmap

This document outlines the development plan for the SmartCFD Trading Agent.

---

## ✅ Section 1: Foundational Setup & Configuration
- [x] Initialize project structure (`pyproject.toml`, basic directories).
- [x] Implement a robust configuration management system (`smartcfd/config.py`).
- [x] Set up structured logging (`smartcfd/logging_setup.py`).
- [x] Create initial Docker setup (`Dockerfile`, `docker-compose.yml`).

## ✅ Section 2: Core Trading Components
- [x] Define abstract base classes for `Broker` and `Strategy`.
- [x] Implement `AlpacaBroker` for paper trading.
- [x] Implement a `DryRunStrategy` for testing the system's core loop.
- [x] Create the main `Trader` class to orchestrate the components.

## ✅ Section 3: Initial Integration & Testing
- [x] Write unit tests for configuration, broker, and strategy components.
- [x] Implement the main application runner (`docker/runner.py`).
- [x] Ensure the `Trader` loop runs correctly in the Docker container.

## ✅ Section 4: Risk Management
- [x] Implement a `RiskManager` class.
- [x] Define risk parameters in the configuration (e.g., max drawdown, position size).
- [x] Integrate `RiskManager` into the `Trader` to approve/reject trades.

## ✅ Section 5: Live Paper Trading
- [x] Connect to Alpaca's paper trading API using environment variables.
- [x] Successfully execute a full trading loop: Strategy -> Risk Manager -> Broker.
- [x] Verify that the bot can run continuously and handle API interactions.

## ✅ Section 6: Baseline ML Model
- [x] Create a data loading module (`smartcfd/data_loader.py`).
- [x] Develop a script to train a baseline `RandomForestClassifier` model (`scripts/train_model.py`).
- [x] Create an `InferenceStrategy` that loads the trained model.
- [x] Integrate the `InferenceStrategy` into the live trading loop.
- [x] **Status:** The bot is now running live with the baseline model.

---

## 🚀 Phase 2: Enhancement & Intelligence

### Section 7: Reporting & Monitoring
- [x] **Daily Digest:** Create a script that generates a daily summary of trades, performance, and decisions.
- [x] **Notifications:** Implement an email service to send out the daily digest and critical alerts.
- [x] **Dashboarding:** Develop a simple web-based dashboard to visualize performance metrics and trade history in real-time.

### Section 8: Advanced Modeling & Prediction Accuracy
- [ ] **Feature Engineering:** Go beyond basic technical indicators. Incorporate features like:
    - Market volatility metrics (e.g., ATR-based).
    - Macroeconomic data or market sentiment indicators.
    - On-chain data for crypto assets.
- [ ] **Experiment with Advanced Models:**
    - **Gradient Boosting:** Test `XGBoost` or `LightGBM`, which often outperform Random Forests.
    - **Time-Series Models:** Explore `LSTMs` or other neural networks designed for sequence data.
- [ ] **Hyperparameter Tuning:** Implement a systematic process (e.g., Grid Search, Bayesian Optimization) to find the optimal settings for the best-performing model.
- [ ] **Ensemble Methods:** Combine predictions from multiple models to improve robustness.

### Section 9: Robustness & Safety Mechanisms
- [ ] **Automated Model Retraining:** Create a workflow to automatically retrain the model on a schedule (e.g., weekly) to adapt to new market data and prevent model drift.
- [ ] **Data Integrity Checks:** Implement a pre-processing step to validate live market data for gaps, staleness, and anomalous values before it's used for inference.
- [ ] **Overfitting Mitigation:** Enhance the training process with rigorous cross-validation and feature importance analysis to ensure the model learns general patterns, not just market noise.
- [x] **Volatility & "Black Swan" Defense:** Upgrade the `RiskManager` to include a circuit breaker that can halt trading or flatten the portfolio if it detects extreme, abnormal market volatility (e.g., a flash crash).
- [ ] **Regime Change Detection:** Research and implement a mechanism to analyze market volatility and correlations to detect shifts in market behavior, potentially allowing the bot to switch between different models or strategies.

### Section 10: Advanced Trading & Portfolio Management
- [ ] **Multi-Asset Trading:** Evolve the bot to analyze and trade a portfolio of multiple assets, not just `BTC/USD`.
- [ ] **Dynamic Risk Management:** Enhance the `RiskManager` to adjust position sizing based on real-time market volatility.
- [ ] **Sophisticated Order Types:** Implement logic for more advanced orders, such as Take Profit and Stop Loss (e.g., trailing stops).

### Section 11: Production & Deployment
- [ ] **Cloud Deployment:** Migrate the application to a cloud VM (e.g., AWS EC2, DigitalOcean Droplet) for 24/7 autonomous operation.
- [ ] **CI/CD Pipeline:** Set up a GitHub Actions workflow to automatically test and deploy new versions of the bot.
- [ ] **Robust Backtesting Engine:** Build a more comprehensive backtester to rapidly and accurately validate new strategies against historical data before live deployment.

---

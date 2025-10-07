This document has been moved to the `docs` directory. Please refer to `docs/ROADMAP.md`.# SmartCFD Trading Agent - Project Roadmap

This document outlines the development plan for the SmartCFD Trading Agent, an automated trading bot using the Alpaca Markets API.

---

## ✅ Phase 1: Core Functionality (Completed)

### Section 1: Foundational Setup & Configuration
- [x] Initialize project structure, `pyproject.toml`, and basic directories.
- [x] Implement a robust configuration management system (`smartcfd/config.py`).
- [x] Set up structured logging (`smartcfd/logging_setup.py`).
- [x] Create initial Docker setup (`Dockerfile`, `docker-compose.yml`).

### Section 2: Core Trading Components
- [x] Define abstract base classes for `Broker` and `Strategy`.
- [x] Implement `AlpacaBroker` for paper trading.
- [x] Implement a `DryRunStrategy` for testing the system's core loop.
- [x] Create the main `Trader` class to orchestrate the components.

### Section 3: Initial Integration & Testing
- [x] Write unit tests for configuration, broker, and strategy components.
- [x] Implement the main application runner (`docker/runner.py`).
- [x] Ensure the `Trader` loop runs correctly in the Docker container.

### Section 4: Risk Management
- [x] Implement a `RiskManager` class.
- [x] Define risk parameters in the configuration (e.g., max drawdown, position size).
- [x] Integrate `RiskManager` into the `Trader` to approve/reject trades.

### Section 5: Live Paper Trading
- [x] Connect to Alpaca's paper trading API using environment variables.
- [x] Successfully execute a full trading loop: Strategy -> Risk Manager -> Broker.
- [x] Verify that the bot can run continuously and handle API interactions.

### Section 6: Baseline ML Model
- [x] Create a data loading module (`smartcfd/data_loader.py`).
- [x] Develop a script to train a baseline model (`scripts/train_model.py`).
- [x] Create an `InferenceStrategy` that loads and uses the trained model.
- [x] Integrate the `InferenceStrategy` into the live trading loop.

---

## ✅ Phase 2: Enhancement & Intelligence (Completed)

### Section 7: Reporting & Monitoring
- [x] **Daily Digest:** Create a script that generates a daily summary of trades, performance, and decisions.
- [x] **Notifications:** Implement an email service to send out the daily digest and critical alerts.
- [x] **Dashboarding:** Develop a simple web-based dashboard to visualize performance metrics and trade history.

### Section 8: Advanced Modeling & Prediction Accuracy
- [x] **Feature Engineering:** Enhance the feature set in `smartcfd/indicators.py` with more sophisticated technical indicators (e.g., Bollinger Bands, MACD, RSI).
- [x] **Hyperparameter Tuning:** Implement `RandomizedSearchCV` to find optimal settings for models.
- [x] **Experiment with Advanced Models:** Replace `RandomForestClassifier` with a tuned `XGBoost` model.

### Section 9: Robustness & Safety Mechanisms
- [x] **Overfitting Mitigation:** Implement feature importance analysis and use `TimeSeriesSplit` for more robust cross-validation suitable for financial data.
- [x] **Volatility & "Black Swan" Defense:** Implement a circuit breaker in the `RiskManager` based on Average True Range (ATR) to halt trading during extreme volatility.

### Section 10: Automated Operations & Maintenance
- [x] **Automated Retraining:** Create a script (`scripts/retrain_model.py`) that automatically retrains the model on a schedule with a rolling data window.
- [x] **Data Integrity Monitoring:** Add robust checks for data gaps, stale data, and anomalies (zero volume, price spikes) in `smartcfd/data_loader.py`.
- [x] **Deployment & Scheduling:** Provide clear documentation for scheduling the trading and retraining scripts on both Windows (`Task Scheduler`) and Linux (`cron`).

---

## ✅ Phase 3: Production Readiness (Completed)

### Section 11: Security & State Management
- [x] **Security Hardening:** Reviewed and hardened the application, ensuring API keys and other secrets are handled securely using a `.env` file with `override=True`.
- [x] **Centralized State Management:** Implemented a central `PortfolioManager` to act as a single source of truth for account state (positions, equity), preventing redundant API calls and ensuring data consistency.
- [x] **Live Trading Preparation:** Added final checks and balances, including explicit warnings and a startup delay when `ALPACA_ENV` is set to `live`.

### Section 12: Testing & Validation
- [x] **Comprehensive Test Suite Repair:** Systematically fixed the entire test suite after major refactoring, ensuring all unit and integration tests pass.
- [x] **Docker Verification:** Completed an extensive, iterative debugging process to resolve a series of startup errors in the Docker container, resulting in a stable and runnable application.

### Section 13: Core Feature Expansion
- [x] **Multi-Asset Trading:** Adapted the system to trade multiple symbols/assets concurrently.
- [x] **Regime Change Detection:** Implemented a mechanism to detect shifts in market volatility (low vs. high).

---

## 🚀 Phase 4: Strategic Improvement & Validation (Current)

*Based on the SWOT analysis, this phase is dedicated to addressing key weaknesses and unlocking new opportunities. The primary focus is on building a robust validation framework and enhancing the predictive power of the model.*

### Section 14: Robust Backtesting Engine
- [ ] **Build Core Backtester:** Develop a script (`scripts/backtest.py`) that can run a strategy against historical data and generate performance metrics.
- [ ] **Performance Metrics:** Implement key metrics like Sharpe Ratio, Sortino Ratio, Max Drawdown, and Win/Loss Rate.
- [ ] **Realistic Simulation:** Ensure the backtester accurately simulates broker commissions, slippage, and order execution delays.
- [ ] **Visualization:** Generate visual reports from backtests, such as equity curves and trade distributions.

### Section 15: Advanced Feature Engineering
- [ ] **Feature Research:** Research and identify new, potentially more predictive features beyond standard technical indicators.
- [ ] **Alternative Data Integration:** Develop a pipeline to incorporate an alternative data source (e.g., on-chain crypto data, market sentiment).
- [ ] **Feature Importance Pipeline:** Refine the process for evaluating the importance of new features and their impact on model performance.

### Section 16: Sophisticated Strategy Development
- [ ] **Develop New Strategy Classes:** Implement new strategy templates (e.g., mean-reversion, momentum-following).
- [ ] **Dynamic Strategies:** Create strategies that can adapt to the market regime detected by the `RegimeDetector` (e.g., use different parameters in high vs. low volatility).
- [ ] **Add Short Selling:** Implement the capability to take short positions.

---

## ☁️ Phase 5: Production & Deployment (Upcoming)

### Section 17: Cloud Deployment
- [ ] **Cloud Deployment:** Migrate the application to a cloud VM (e.g., AWS EC2, DigitalOcean Droplet) for 24/7 autonomous operation.
- [ ] **CI/CD Pipeline:** Set up a GitHub Actions workflow to automatically test and deploy new versions of the bot.

---

## 📚 Phase 6: Review & Documentation (Ongoing)

### Section 18: Continuous Improvement
- [ ] **Performance Review:** Continuously evaluate the trading bot's performance against initial objectives and benchmarks.
- [ ] **Roadmap Revision:** Revise the project roadmap based on new findings and priorities.
- [ ] **Documentation:** Keep all project documents (`PROJECT_SUMMARY.md`, `LESSONS_LEARNED.md`, etc.) up-to-date with the latest developments.

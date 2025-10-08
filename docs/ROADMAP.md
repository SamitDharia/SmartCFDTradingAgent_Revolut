# Development Roadmap

This document outlines the strategic development phases for the Smart CFD Trading Agent, reflecting the project's evolution from inception to its current state.

---

### Phase 1: Core Functionality & Foundation (Completed)

This phase established the project's groundwork and core architecture.

- [x] **Initial Setup**: Configured the development environment with Docker, Git, and VS Code.
- [x] **Modular Architecture**: Designed and implemented the core classes: `Broker`, `Strategy`, `RiskManager`, and `PortfolioManager`.
- [x] **Alpaca Integration**: Connected to the Alpaca paper trading API for market data and order execution.
- [x] **Baseline ML Model**: Created an initial machine learning pipeline using `RandomForestClassifier`.
- [x] **Containerization**: Dockerized the application for portable and reproducible deployment.
- [x] **Basic Logging**: Implemented structured logging to monitor the application's behavior.

---

### Phase 2: Intelligence & Safety (Completed)

This phase focused on enhancing the model's intelligence and implementing critical safety mechanisms.

- [x] **Advanced Modeling**: Upgraded the model from `RandomForestClassifier` to a tuned `XGBoost` classifier for better performance.
- [x] **Hyperparameter Tuning**: Implemented a systematic process for finding the best model parameters using `RandomizedSearchCV`.
- [x] **Feature Engineering**: Enhanced the feature set with a wide array of technical indicators (Bollinger Bands, MACD, RSI, etc.).
- [x] **Volatility Circuit Breaker**: Implemented an ATR-based mechanism in the `RiskManager` to halt trading during extreme market volatility.
- [x] **Overfitting Mitigation**: Used `TimeSeriesSplit` for cross-validation to build more generalizable models.
- [x] **Data Integrity Monitoring**: Added robust checks for data gaps, stale data, and anomalies to prevent trading on bad data.

---

### Phase 3: Automation, Reporting & Testing (Completed)

This phase automated key processes and built a robust validation framework.

- [x] **Automated Retraining Pipeline**: Created a script (`scripts/retrain_model.py`) to automatically retrain the model on a rolling basis.
- [x] **Daily Digest Reporting**: Implemented a script (`scripts/daily_summary.py`) to generate and email a daily performance summary.
- [x] **Backtesting Engine**: Built a script (`scripts/backtest.py`) to evaluate strategy performance on historical data.
- [x] **Comprehensive Test Suite**: Achieved high test coverage with `pytest`, including a full integration test (`tests/test_full_system_run.py`) to validate the entire trading loop.
- [x] **State Management & Debugging**: Centralized portfolio state management and resolved complex bugs related to environment, configuration, and data flow.
- [x] **Intelligent Health Checks**: Implemented a `/healthz` endpoint that performs a full check on all critical components before reporting a healthy status.

---

### Phase 4: Advanced Trading & Production Hardening (Completed)

This phase introduced sophisticated trading logic and hardened the system for stability.

- [x] **Market Regime Detection**: Implemented a `RegimeDetector` to classify market conditions, allowing the strategy to adapt.
- [x] **Multi-Symbol Trading**: Enabled the agent to trade multiple symbols concurrently, with risk managed on a per-trade basis.
- [x] **Advanced Risk Management**: Implemented dynamic, ATR-based stop-loss and take-profit orders, with position sizes calculated based on a fixed risk percentage.
- [x] **Real-time Data Handling**: Switched to using the `get_crypto_snapshot` endpoint for live data to ensure accuracy and prevent trading on partial bars.
- [x] **Code Hardening & Stability**: Performed extensive data validation, error handling, and stability fixes based on integration test findings and live paper trading.
- [x] **Startup Grace Period**: Added a 60-second grace period to the health check to prevent failures during application initialization in Docker.

---

### Phase 5: Future Enhancements & Live Deployment (Next Steps)

This phase focuses on deploying the agent to a live environment and continuously improving its capabilities.

- [ ] **Data Feed Redundancy & Health**: Decouple data from execution. Integrate a primary, exchange-native data feed (e.g., Kraken, Coinbase) and use Alpaca as a fallback and for order execution. Implement a "data-health gate" to validate data quality in real-time and backfill gaps.
- [ ] **Enhanced Monitoring and Alerting**: Implement a more sophisticated monitoring solution (e.g., Prometheus/Grafana) and set up alerts for critical events.
- [ ] **Cloud Deployment & CI/CD**: Deploy the agent to a cloud environment (e.g., AWS, GCP) and establish a continuous integration and deployment pipeline.
- [ ] **Advanced Data Integration**: Research and integrate non-price-based data sources (e.g., news sentiment, on-chain metrics) to improve model performance.
- [ ] **Live Trading**: After extensive testing and validation in the paper environment, transition the agent to live trading with real capital.

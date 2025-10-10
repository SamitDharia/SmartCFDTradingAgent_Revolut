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

### Phase 4A: Live Paper Trading & Validation (V1.0 - In Progress)

This phase focuses on validating the agent's end-to-end functionality in a live paper trading environment. The goal is to build confidence in its decision-making and execution capabilities before considering it "complete."

**Accomplishments (System Hardening):**
- [x] **Market Regime Detection**: Implemented a `RegimeDetector` to classify market conditions, allowing the strategy to adapt.
- [x] **Multi-Symbol Trading**: Enabled the agent to trade multiple symbols concurrently, with risk managed on a per-trade basis.
- [x] **Advanced Risk Management**: Implemented dynamic, ATR-based stop-loss and take-profit orders, with position sizes calculated based on a fixed risk percentage.
- [x] **Real-time Data Handling**: Switched to using the `get_crypto_snapshot` endpoint for live data to ensure accuracy and prevent trading on partial bars.
- [x] **Code Hardening & Stability**: Performed extensive data validation, error handling, and stability fixes based on integration test findings. This included a deep debugging session to resolve a cascade of interacting issues, resulting in a truly stable system.
- [x] **Startup Grace Period**: Added a 60-second grace period to the health check to prevent failures during application initialization in Docker.

**V1.0 Completion Criteria (To-Do):**
- [ ] **Verify End-to-End Trade Execution**: Observe the agent autonomously execute multiple trades (both simple and complex, with stop-loss/take-profit) in the live paper market.
- [ ] **Confirm Autonomous Learning Loop**: Ensure the agent can run for an extended period, automatically retrain its model, and continue trading with the updated model without manual intervention.
- [ ] **Achieve Decision-Making Confidence**: Monitor trading decisions over a sustained period to ensure they are logical, profitable, and align with the strategy's intent. V1.0 is complete only when we trust its ability to manage capital.

---

### Phase 4B: Live Performance Analysis & Calibration

**Status:** In Progress

**Objective:** Analyze the live performance of the V1 model and calibrate its parameters based on real-world data.

**Key Tasks:**
- [x] **Log All Prediction Probabilities:** Modified the `InferenceStrategy` to log the full probability array (`[hold, buy, sell]`) for every single evaluation. This will create a dataset of the model's confidence over time. *(Note: Implemented via a temporary `print` statement for immediate visibility.)*
- [ ] **Analyze Confidence Distribution:** After a data collection period (e.g., 24-48 hours), analyze the distribution of the logged probabilities. Determine the model's actual confidence range (min, max, average) for 'buy' and 'sell' signals.
- [ ] **Calibrate `trade_confidence_threshold`:** Based on the analysis, make an informed, data-driven decision on whether to adjust the `trade_confidence_threshold` in `config.ini` to a more realistic value for the current model.
- [ ] **Assess Model Viability:** Conclude whether the model is fundamentally capable of producing actionable signals or if it requires retraining with different features or a different architecture.

---

### Phase 5: Professional-Grade Trading & Multi-Broker Support (Future Vision)

This phase will begin *after* V1.0 is validated and complete. It will evolve the agent from a single-broker system into a professional-grade, broker-agnostic trading platform, ensuring V1 remains a stable, separate foundation.

1.  **Foundational Architecture (V2 Groundwork)**:
    - [ ] **Broker-Agnostic Architecture**: Refactor the core trading logic to be independent of any single broker. Create a standardized `Broker` interface and implement separate adapters for each supported broker (e.g., `AlpacaAdapter`, `InteractiveBrokersAdapter`). This is the cornerstone of V2.

2.  **Expansion & Intelligence**:
    - [ ] **Interactive Brokers (IBKR) Integration**: Integrate the IBKR API to gain access to a vastly wider range of markets, including stocks, options, futures, and forex.
    - [ ] **CCXT Library Integration**: For cryptocurrency trading, integrate the `CCXT` library to connect to over 100 crypto exchanges for data redundancy and arbitrage opportunities.
    - [ ] **Formal Quantitative Modeling**: Transition from a pure ML approach to a hybrid quant model, systematically researching and validating specific "alpha factors" (e.g., momentum, mean-reversion).
    - [ ] **Portfolio-Level Optimization**: Implement Modern Portfolio Theory (MPT) to optimize capital allocation across a basket of assets.

3.  **Deployment & Validation**:
    - [ ] **Cloud Deployment & CI/CD**: Deploy the V2 agent to a cloud environment (e.g., AWS, GCP) and establish a CI/CD pipeline.
    - [ ] **V2 Paper Trading**: Conduct a dedicated, extensive paper trading phase for the new V2 architecture to validate its performance and stability.
    - [ ] **Enhanced Monitoring**: Implement a sophisticated monitoring solution (e.g., Prometheus/Grafana) for critical alerts.
    - [ ] **V2 Live Deployment**: After successful paper trading, transition the V2 agent to live trading with a small, controlled capital allocation.

### Phase 6: Autonomous Intelligence (Long-Term Vision)

- [ ] **Dynamic Model & Strategy Switching**: Implement a master-model that dynamically selects the best underlying ML model or trading strategy based on the detected market regime.
- [ ] **Alternative Data Integration**: Integrate non-price-based data sources, such as news sentiment or on-chain metrics.
- [ ] **Explainable AI (XAI) for Trading Decisions**: Integrate tools like SHAP to provide clear explanations for why the model made a specific trade decision.
- [ ] **Reinforcement Learning (RL) Core**: Research and implement a Reinforcement Learning agent that learns an optimal trading policy directly from market interaction.
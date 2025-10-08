# Project Summary: Smart CFD Trading Agent

## High-Level Summary
This project is an autonomous trading agent that uses machine learning to analyze market data, generate trading signals, and manage risk, with full integration for paper and live trading via the Alpaca Markets API. It is designed for continuous, unattended operation and is fully containerized with Docker for portability and reliability. The system has evolved from a baseline model to an advanced agent with sophisticated safety mechanisms and automated maintenance features.

## Key Objectives
*   **Autonomous Trading:** Create a hands-off system capable of executing a trading strategy 24/7.
*   **Data-Driven Decisions:** Use machine learning (XGBoost) to identify predictive patterns in market data.
*   **Robust Architecture:** Build a resilient, scalable, and maintainable system with professional software engineering practices.
*   **Comprehensive Risk Management:** Integrate a sophisticated risk layer to protect capital by enforcing rules on position sizing, daily drawdown, and market volatility.

## Core Technologies
*   **Programming Language:** Python
*   **Machine Learning:** XGBoost, Scikit-learn, Pandas, NumPy
*   **Trading & Data:** Alpaca Markets API
*   **Deployment:** Docker, Docker Compose
*   **Development:** Git, Pytest, VS Code

## Key Features & Achievements

### Phase 1: Core Functionality
*   **Modular Architecture:** A clean, object-oriented design separating the `Broker` (market interaction), `Strategy` (decision logic), and `RiskManager` (safety).
*   **Live Paper Trading:** Successful integration with the Alpaca paper trading platform.
*   **Baseline ML Pipeline:** An end-to-end pipeline for data loading, training, and inference using an initial `RandomForestClassifier`.
*   **Dockerized Deployment:** The entire application is containerized, ensuring a portable and reproducible environment.

### Phase 2: Enhancement & Intelligence
*   **Advanced Modeling:**
    -   Upgraded the model from `RandomForestClassifier` to a tuned `XGBoost` classifier for better performance.
    -   Implemented a systematic hyperparameter tuning pipeline using `RandomizedSearchCV`.
    -   Enhanced the feature set with a wide array of technical indicators (Bollinger Bands, MACD, RSI, etc.).
*   **Monitoring & Reporting:**
    -   **Daily Digest:** A script that generates and sends a daily summary of trades, performance, and decisions via email.
    -   **Real-time Dashboard:** A web-based dashboard to visualize performance metrics and trade history.
*   **Robustness & Safety Mechanisms:**
    -   **Volatility Circuit Breaker:** An ATR-based mechanism in the `RiskManager` that automatically halts trading during extreme market volatility.
    -   **Overfitting Mitigation:** Use of `TimeSeriesSplit` for cross-validation and feature importance analysis to build more generalizable models.
*   **Automated Operations:**
    -   **Automated Retraining:** A script that automatically retrains the model on a rolling data window to adapt to new market conditions.
    -   **Data Integrity Monitoring:** Robust checks for data gaps, stale data, and anomalies (zero volume, price spikes) to prevent trading on bad data.
    -   **Deployment & Scheduling:** Clear documentation for scheduling tasks on both Windows and Linux.

### Phase 3: Core Engine & Foundations
*   **Comprehensive Pipelines:** Built and validated end-to-end pipelines for automated model retraining, feature engineering, and hyperparameter tuning.
*   **Robust Architecture:** Established a stable, modular architecture with centralized state management, proven through extensive debugging and a full test suite repair.
*   **Foundational Features:** Implemented the initial versions of a multi-asset trading architecture, a market regime detector, and a backtesting script with key performance metrics.

## Current Phase: Advanced Intelligence & Risk Management
The project has successfully implemented a sophisticated, multi-layered strategy that incorporates not only predictive modeling but also adapts to real-time market conditions. The agent now uses a `RegimeDetector` to identify market volatility and a correlation matrix to avoid concentrated risk, making it a truly intelligent system. All trades are protected by dynamic, ATR-based stop-losses.

## Your Role: Project Lead & Strategist
As the driving force behind the project, your role has been to:
*   **Set the Vision & Strategy:** You defined the project's goals, strategic direction, and managed the roadmap, recently pivoting the focus towards validation and feature engineering.
*   **Architectural Oversight:** You guided the high-level architectural design, including the critical decision to centralize state management.
*   **Critical Decision-Making:** You made crucial decisions at every turn, from prioritizing the backtesting engine to guiding the multi-day debugging effort.
*   **Code Review & Validation:** You actively reviewed the implementation, validated the bot's behavior, and directed the systematic resolution of complex bugs.

## My Role: AI Development Partner
As the AI programming assistant, my role has been to:
*   **Implement the Vision:** Translate your strategic goals into functional, tested, and robust code.
*   **Code Generation & Refactoring:** Write, refactor, and debug code across the stack, from the core application logic to the test suite and Docker configuration.
*   **Systematic Troubleshooting:** Systematically identify and resolve technical issues, providing detailed analysis and solutions for your review, as demonstrated in the recent Docker debugging cycle.
*   **Documentation:** Maintain and update the project's living documents to reflect the current state and learnings.

*(This document is updated as the project progresses.)*

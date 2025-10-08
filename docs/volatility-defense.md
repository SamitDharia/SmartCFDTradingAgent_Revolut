# Volatility & Market Regime Defense

This document outlines the mechanisms implemented to protect the trading agent from extreme market volatility and to allow it to adapt its strategy to different market conditions.

## 1. Market Regime Detection

A core enhancement to the agent's intelligence is the `RegimeDetector`, which classifies the market into different states or "regimes." This allows the strategy to behave differently in, for example, a stable, low-volatility market versus a chaotic, high-volatility one.

### How It Works
1.  **ATR-Based Calculation**: The detector uses two Average True Range (ATR) calculations on the historical price data: a short-window ATR (e.g., 14 periods) to measure current volatility and a long-window ATR (e.g., 50 periods) to measure baseline volatility.
2.  **Regime Classification**:
    *   If the short-term ATR is significantly higher (e.g., > 1.25x) than the long-term ATR, the market is classified as **`HIGH_VOLATILITY`**.
    *   Otherwise, it is classified as **`LOW_VOLATILITY`**.
3.  **Strategy Adaptation**: The detected regime is passed to the `Strategy` module, which can use this information to adjust its logic. For example, it might avoid taking trades in a high-volatility regime or use different parameters.

### Tuning for Stability
During development, the `RegimeDetector` was a key factor in system stability. Initially, it required 100 data points (`long_window=100`), which caused "insufficient data" errors when the data loader could not provide enough valid historical bars. To resolve this, the parameters were tuned to be less demanding:
-   `short_window` was set to **14**.
-   `long_window` was set to **50**.

This change ensured the detector could operate reliably even with a smaller set of clean data, which was critical to allowing the full trading pipeline to execute.

## 2. Volatility Circuit Breaker

The circuit breaker is a risk management feature designed to automatically halt trading for a specific asset when its immediate volatility spikes unexpectedly.

### How It Works

1.  **Data Collection**: The `Strategy` module provides the historical price data (High, Low, Close) that was used to generate the trading signal.
2.  **Volatility Calculation**: The `RiskManager.is_volatility_too_high` method calculates the **True Range (TR)** of the most recent price bar.
3.  **Threshold Comparison**: This latest True Range value is then compared against a dynamic threshold. The threshold is calculated by taking the **average of the 14-period ATR** (excluding the most recent bar) and multiplying it by a configurable multiplier.
4.  **Tripping the Breaker**: If the latest True Range exceeds this threshold, the circuit breaker is "tripped."
5.  **Halting Trades**: When the breaker is tripped for a symbol, the `Trader` will log a warning and refuse to execute any new `buy` or `sell` orders for that symbol during the current trading cycle.

### Configuration

-   **`circuit_breaker_atr_multiplier`**: This float determines the sensitivity of the circuit breaker. A value of `3.0` (the default) means trading will be halted if the most recent bar's True Range is more than 3 times the recent average ATR. Setting this to `0` disables the feature.

## 3. Synergy of Regime and Circuit Breaker

These two features work together to provide a comprehensive defense against volatility:
-   The **Regime Detector** provides a high-level, strategic view of the market's state, allowing the model to adapt its approach over time.
-   The **Circuit Breaker** provides a low-level, tactical defense against sudden, immediate price shocks.

This layered approach ensures the agent operates within predictable market conditions and automatically steps aside during periods of dangerous instability.

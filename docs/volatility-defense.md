# Volatility & "Black Swan" Defense

This document outlines the "circuit breaker" mechanism implemented to protect the trading agent from extreme market volatility, often associated with "black swan" events.

## 1. Overview

The circuit breaker is a risk management feature designed to automatically halt trading for a specific asset when its market volatility exceeds a predefined threshold. This prevents the agent from entering new positions during periods of extreme price fluctuation, which can lead to significant and unpredictable losses.

The core of this mechanism is based on the **Average True Range (ATR)**, a common technical analysis indicator that measures market volatility.

## 2. How It Works

Before executing any `buy` or `sell` order, the `Trader` performs a volatility check using the `RiskManager`. Here's the process:

1.  **Data Collection**: The `Strategy` module provides the historical price data (High, Low, Close) that was used to generate the trading signal.

2.  **Volatility Calculation**: The `RiskManager.is_volatility_too_high` method calculates the **True Range (TR)** of the most recent price bar. The True Range is the greatest of the following:
    *   The current high minus the current low.
    *   The absolute value of the current high minus the previous close.
    *   The absolute value of the current low minus the previous close.

3.  **Threshold Comparison**: This latest True Range value is then compared against a dynamic threshold. The threshold is calculated by taking the **average of the 14-period ATR** (excluding the most recent bar) and multiplying it by a configurable multiplier.

4.  **Tripping the Breaker**: If the latest True Range exceeds this threshold, the circuit breaker is "tripped."

5.  **Halting Trades**: When the breaker is tripped for a symbol, the `Trader` will log a warning and refuse to execute any new `buy` or `sell` orders for that symbol during the current trading cycle.

## 3. Configuration

The behavior of the circuit breaker is controlled by a single parameter in `smartcfd/config.py` and can be set via environment variables.

-   **`circuit_breaker_atr_multiplier`** (`CIRCUIT_BREAKER_ATR_MULTIPLIER` env var)
    -   **Description**: This floating-point number determines the sensitivity of the circuit breaker. It's the multiplier applied to the average ATR to set the threshold.
    -   **Default Value**: `3.0`
    -   **Behavior**:
        -   A value of `3.0` means that trading will be halted if the most recent bar's True Range is more than 3 times the recent average ATR.
        -   Setting this value to `0` or a negative number effectively **disables** the circuit breaker.
    -   **Tuning**: A higher value makes the breaker less sensitive (requiring more extreme volatility to trip), while a lower value makes it more sensitive. The default of `3.0` is a common starting point, representing a significant deviation from recent volatility.

## 4. Rationale

-   **Protection Against Spikes**: The primary goal is to defend against sudden, anomalous price spikes that can occur during news events, market manipulation, or flash crashes.
-   **Dynamic Threshold**: Using a multiple of the recent average ATR allows the threshold to adapt to the asset's normal volatility. A normally volatile asset will have a wider threshold than a typically stable one.
-   **Immediate Response**: By checking the True Range of the most recent bar, the system can react immediately to a sudden spike, rather than waiting for the spike to be smoothed into a longer-period ATR calculation.

This mechanism adds a critical layer of safety, ensuring the agent operates within predictable market conditions and automatically steps aside during periods of dangerous instability.

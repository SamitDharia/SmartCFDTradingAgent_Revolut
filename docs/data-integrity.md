
## Data Integrity Checks

To enhance the robustness of the trading agent, a series of data integrity checks have been implemented in `smartcfd/data_loader.py`. These checks run every time the `InferenceStrategy` evaluates market data, ensuring that the model only makes predictions based on data that is timely, complete, and sensible.

If any of these checks fail, the strategy will halt the trade evaluation for that cycle and log a "hold" decision with a specific reason, preventing orders based on faulty data.

### Implemented Checks

1.  **`is_data_stale(df, max_staleness_minutes)`**
    *   **Purpose:** To ensure the market data is recent.
    *   **Logic:** It compares the timestamp of the latest data point against the current UTC time. If the difference exceeds a configurable threshold (`max_data_staleness_minutes`), the data is considered stale.
    *   **Reason Code:** `data_stale`

2.  **`has_data_gaps(df, expected_interval)`**
    *   **Purpose:** To detect missing bars in the time-series data.
    *   **Logic:** It reconstructs the expected timeline of timestamps based on the start and end times of the data and the known frequency (e.g., every 15 minutes). It then checks if any expected timestamps are missing from the actual data.
    *   **Reason Code:** `data_gaps_detected`

3.  **`has_anomalous_data(df, anomaly_threshold)`**
    *   **Purpose:** To check for obviously incorrect or suspicious data values.
    *   **Logic:** It scans the data for several types of anomalies:
        *   **Empty Data:** Fails if the DataFrame is empty.
        *   **Zero or Negative Prices:** Fails if any value in the `open`, `high`, `low`, or `close` columns is zero or less.
        *   **Zero Volume with Price Movement:** Fails if a bar has a `volume` of 0 but the `high` and `low` prices are different, which is a logical impossibility.
        *   **Price Spikes:** Fails if the range (`high` - `low`) of the most recent bar is drastically larger (e.g., 5x) than the average range of the preceding bars. This acts as a simple "flash crash" or data error detector.
    *   **Reason Code:** `anomalous_data_detected`

### Configuration

The behavior of these checks can be configured via `configs/*.yml` files or environment variables:
-   **Staleness:** The `max_data_staleness_minutes` parameter controls the time window for the staleness check.
-   **Anomaly Threshold:** The `anomaly_threshold` parameter controls the sensitivity of the price spike detection (default is 5.0).


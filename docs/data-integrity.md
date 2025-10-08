
## Data Integrity & Validation

To ensure the trading agent operates on reliable and accurate information, a multi-layered data integrity and validation process is implemented in `smartcfd/data_loader.py`. These checks are performed every time market data is fetched, preventing the model from making predictions based on faulty data.

### Data Loading Process (`get_market_data`)

The data loading process was significantly enhanced to improve stability and accuracy:

1.  **Historical + Snapshot Fetching**: Instead of relying solely on historical bar data, which can provide incomplete bars for the current time interval, the system now fetches a larger set of historical bars and combines it with the latest **snapshot data** from the `get_crypto_snapshot` endpoint.
2.  **Data Combination**: The snapshot's bar data (e.g., `minute_bar`) is used to update or replace the most recent historical bar. This ensures the latest data is always complete and accurate up to the last full minute.
3.  **Anomaly Removal**: The combined data is then passed through a cleaning function (`remove_zero_volume_anomalies`) to handle specific data quality issues.
4.  **Validation Checks**: Finally, the cleaned data is subjected to a series of validation checks before being returned to the strategy.

### Implemented Checks

1.  **Zero Volume Anomaly (`remove_zero_volume_anomalies`)**
    *   **Purpose:** To handle bars that show price movement (`high` != `low`) but have zero `volume`. This is a logical impossibility and a common indicator of bad data from an exchange.
    *   **Logic:** The function identifies these anomalous bars.
    *   **Action:** Initially, this function removed the bad data. However, during debugging, it was found that removing this data could lead to insufficient data for downstream processes (like the `RegimeDetector`). The function was modified to **log a warning** about the anomaly but **keep the data** to ensure system stability.

2.  **Data Gap Check (`has_data_gaps`)**
    *   **Purpose:** To detect missing bars in the time-series data.
    *   **Logic:** It reconstructs the expected timeline of timestamps based on the data's start/end times and the known frequency (e.g., every 15 minutes). It then checks if any expected timestamps are missing.
    *   **Tolerance:** To prevent failures from minor, temporary data provider issues, a `tolerance` parameter was introduced. The check now only fails if the percentage of missing data exceeds this tolerance (e.g., 10%).

3.  **Staleness Check (`is_data_stale`)**
    *   **Purpose:** To ensure the market data is recent.
    *   **Logic:** It compares the timestamp of the latest data point against the current UTC time. If the difference exceeds a configurable threshold (`max_data_staleness_minutes`), the data is considered stale.

4.  **Anomalous Value Check (`has_anomalous_data`)**
    *   **Purpose:** To check for obviously incorrect or suspicious data values.
    *   **Logic:** It scans the data for several types of anomalies:
        *   Empty DataFrames.
        *   Zero or negative prices in OHLC columns.
        *   Sudden price spikes where the most recent bar's range is drastically larger than the recent average.

If any of these validation checks fail, the data for that symbol is invalidated for the current trading cycle, preventing the model from acting on it.


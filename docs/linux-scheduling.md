# Scheduling Tasks on Linux with Cron

This guide explains how to automate periodic tasks for the SmartCFDTradingAgent on a Linux system using `cron`.

---

## Running the Main Trading Agent

The main trading agent in V1.0 is designed as a **continuous, long-running service**. It is **not** meant to be triggered by a scheduler like `cron` for each trade.

To run the agent, simply start it once using Docker Compose:

```bash
# Navigate to the project directory
cd /path/to/your/SmartCFDTradingAgent_Revolut

# Build the image if you haven't already
docker compose build

# Start the agent in detached mode
docker compose up -d
```

The agent will run in the background, and its internal loop (defined in `docker/runner.py`) will handle the trading frequency based on the `run_interval_seconds` setting in `config.ini`.

## Scheduling Automated Model Retraining

While the main agent runs continuously, `cron` is the perfect tool for scheduling periodic maintenance tasks like retraining the model. The `docker-compose.yml` file includes a dedicated `retrain` service for this purpose.

### Steps

1.  **Edit your crontab**:
    Open the crontab editor with the command:
    ```bash
    crontab -e
    ```

2.  **Add the cron job entry**:
    To run the automated retraining script (e.g., every Sunday at 2:00 AM), add the following line. This command navigates to your project directory and runs the `retrain` service.

    ```cron
    0 2 * * 0 cd /path/to/your/SmartCFDTradingAgent_Revolut && docker-compose run --rm retrain >> /path/to/your/SmartCFDTradingAgent_Revolut/logs/retraining.log 2>&1
    ```

    **Explanation**:
    -   `0 2 * * 0`: Runs the command at 2:00 AM every Sunday.
    -   `cd /path/to/your/SmartCFDTradingAgent_Revolut`: **Absolute path** to your project's root directory.
    -   `docker-compose run --rm retrain`: Executes the `retrain` service defined in `docker-compose.yml`. The `--rm` flag automatically removes the container after it exits, which is ideal for scheduled tasks.
    -   `>> .../logs/retraining.log 2>&1`: Redirects all output (both standard and error) to a log file within your project's `logs` directory for later review.

3.  **Save and Exit**:
    -   If using `nano`, press `Ctrl+X`, then `Y`, then `Enter`.
    -   If using `vim`, press `Esc`, then type `:wq`, then `Enter`.

4.  **Verify**:
    List your active cron jobs to ensure it's saved:
    ```bash
    crontab -l
    ```
    After the scheduled time, you can check the log file for the output of the retraining script:
    ```bash
    tail -f /path/to/your/SmartCFDTradingAgent_Revolut/logs/retraining.log
    ```


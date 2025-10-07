# Scheduling the Trading Agent on Linux with Cron

This guide explains how to automate the execution of the SmartCFDTradingAgent on a Linux system using `cron`. `cron` is a time-based job scheduler in Unix-like computer operating systems. This guide covers two approaches: running with Docker Compose and running directly with Python.

---

## Approach 1: Using Docker Compose (Recommended)

This is the recommended approach as it encapsulates the environment and dependencies within a Docker container, making it more reliable and portable.

### Prerequisites
- Docker and Docker Compose are installed.
- The project is cloned on your Linux machine.

### Steps
1.  **Edit your crontab**:
    Open the crontab editor with the command:
    ```bash
    crontab -e
    ```

2.  **Add the cron job entry**:
    To run the trading agent every 15 minutes, add the following line. This command navigates to your project directory and runs the `trader` service defined in `docker-compose.yml`.

    ```cron
    */15 * * * * cd /path/to/your/SmartCFDTradingAgent_Revolut && docker-compose run --rm trader >> /var/log/smartcfd/cron.log 2>&1
    ```

    **Explanation**:
    - `*/15 * * * *`: Runs the command every 15 minutes.
    - `cd /path/to/your/SmartCFDTradingAgent_Revolut`: **Absolute path** to your project's root directory.
    - `docker-compose run --rm trader`: Executes the `trader` service. `docker-compose run` starts a one-off instance of the service. The `--rm` flag automatically removes the container after it exits, which is ideal for scheduled tasks.
    - `>> /var/log/smartcfd/cron.log 2>&1`: Redirects all output (both standard and error) to a log file. It's good practice to create a dedicated log directory.

3.  **Save and Exit**:
    - If using `nano`, press `Ctrl+X`, then `Y`, then `Enter`.
    - If using `vim`, press `Esc`, then type `:wq`, then `Enter`.

4.  **Verify**:
    List your active cron jobs to ensure it's saved:
    ```bash
    crontab -l
    ```
    After 15 minutes, check the log file:
    ```bash
    tail -f /var/log/smartcfd/cron.log
    ```

---

## Approach 2: Using a Python Virtual Environment

This approach runs the script directly on the host machine. It requires careful management of the Python environment and dependencies.

### Prerequisites
- A dedicated Python virtual environment is set up.
- All dependencies from `requirements.txt` are installed in the virtual environment.
- Environment variables (e.g., `API_KEY`, `API_SECRET`) are configured.

### Steps
1.  **Create a Runner Script**:
    Create a shell script to activate the environment and run the trader. Create `scripts/run_trader.sh`:
    ```bash
    #!/bin/bash

    # Navigate to the project's root directory
    cd /path/to/your/SmartCFDTradingAgent_Revolut

    # Activate your Python virtual environment
    source /path/to/your/venv/bin/activate

    # Run the trader module
    python -m smartcfd.trader
    ```
    Make the script executable:
    ```bash
    chmod +x scripts/run_trader.sh
    ```

2.  **Set up the Cron Job**:
    Open the crontab editor (`crontab -e`) and add the following entry to run the script every 15 minutes:
    ```cron
    */15 * * * * /path/to/your/SmartCFDTradingAgent_Revolut/scripts/run_trader.sh >> /var/log/smartcfd/cron.log 2>&1
    ```

### Scheduling Other Scripts
The same logic applies to other scripts like automated retraining or daily digests.

**Example: Run automated model retraining at 2 AM every Sunday:**
```cron
# Using Docker Compose
0 2 * * 0 cd /path/to/your/SmartCFDTradingAgent_Revolut && docker-compose run --rm retrain >> /var/log/smartcfd/retrain_cron.log 2>&1

# Using Python direct execution (assuming a run_retrain.sh script)
0 2 * * 0 /path/to/your/SmartCFDTradingAgent_Revolut/scripts/run_retrain.sh >> /var/log/smartcfd/retrain_cron.log 2>&1
```
To support this, you would need to add a `retrain` service to your `docker-compose.yml` file that runs `scripts/retrain_model.py`.

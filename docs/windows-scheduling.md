# Scheduling the Trading Agent on Windows with Task Scheduler

This guide explains how to automate the execution of the SmartCFDTradingAgent on a Windows system using the built-in Task Scheduler. This guide covers two approaches: running with Docker Compose and running directly with Python.

---

## Approach 1: Using Docker Compose (Recommended)

This method is robust as it uses Docker to manage the environment and dependencies.

### Steps
1.  **Open Task Scheduler**: Search for "Task Scheduler" in the Start Menu and open it.

2.  **Create a New Task**: In the right-hand pane, click **Create Task...** (do not use "Create Basic Task" as it offers fewer options).

3.  **General Tab**:
    -   **Name**: Give your task a descriptive name, e.g., "Run SmartCFD Trader".
    -   **Security options**: Select "Run whether user is logged on or not" to ensure the task runs even if you are not signed in.

4.  **Triggers Tab**:
    -   Click **New...**.
    -   Configure the schedule. To run the task every 15 minutes:
        -   Select **Daily**.
        -   Under **Advanced settings**, check **Repeat task every** and select **15 minutes** from the dropdown.
        -   Set the duration to **Indefinitely**.
        -   Ensure **Enabled** is checked.
        -   Click **OK**.

5.  **Actions Tab**:
    -   Click **New...**.
    -   **Action**: Select **Start a program**.
    -   **Program/script**: Enter `docker-compose`.
    -   **Add arguments (optional)**: Enter `run --rm trader`. This command starts a one-off instance of the `trader` service and removes the container after it exits.
    -   **Start in (optional)**: Enter the **absolute path** to your project's root directory (e.g., `C:\Projects\SmartCFDTradingAgent_Revolut`). This is crucial for `docker-compose` to find the `docker-compose.yml` file.
    -   Click **OK**.

6.  **Settings Tab**:
    -   Review the settings. You might want to check "Stop the task if it runs longer than:" and set a reasonable duration (e.g., 10 minutes) to prevent runaway processes.

7.  **Save the Task**:
    -   Click **OK**. You will be prompted to enter the password for the user account the task will run as.

---

## Approach 2: Using a Python Virtual Environment

This approach runs the script directly on the host.

### Steps
1.  **Create a Batch Script**:
    Create a file named `run_trader.bat` in your `scripts` folder with the following content:
    ```batch
    @echo off
    
    :: Navigate to the project's root directory
    cd /d "C:\Projects\SmartCFDTradingAgent_Revolut"
    
    :: Activate the Python virtual environment
    call "C:\path\to\your\venv\Scripts\activate.bat"
    
    :: Run the trader module
    python -m smartcfd.trader
    ```
    Replace the paths with the correct ones for your system.

2.  **Configure Task Scheduler**:
    -   Follow the same steps as in Approach 1, but for the **Actions** tab:
        -   **Program/script**: Enter the full path to your batch script, e.g., `C:\Projects\SmartCFDTradingAgent_Revolut\scripts\run_trader.bat`.
        -   Leave the "Add arguments" and "Start in" fields blank, as they are handled inside the batch file.

### Logging and Debugging
For both approaches, the Python application's logging configuration (in `smartcfd/logging_setup.py`) will determine where logs are written. When running as a scheduled task, it's essential that the application logs to a file, as you won't be able to see console output directly. Ensure your logging setup is configured to write to a file in a location like the `logs/` directory.

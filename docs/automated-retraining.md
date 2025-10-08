
## Automated Model Retraining

To prevent model drift and ensure the trading agent adapts to new market conditions, an automated retraining workflow has been implemented.

### How It Works

The `scripts/retrain_model.py` script is designed to be run on a schedule (e.g., weekly). It performs the following steps:

1.  **Checks Model Age:** It checks the last modification date of the `models/model.joblib` file.
2.  **Triggers Retraining:** If the model is older than a defined threshold (currently 7 days), it automatically kicks off the full training and evaluation pipeline. This includes:
    *   Fetching the latest data.
    *   Performing hyperparameter tuning (`RandomizedSearchCV`).
    *   Evaluating the best model.
    *   Saving the newly trained model to `models/model.joblib`.
3.  **Skips if Fresh:** If the model is up-to-date, the script logs a message and exits without taking any action.

### Scheduling the Retraining Script

You can automate this process using your operating system's task scheduler.

#### Cron (Linux/macOS)

You can edit your crontab to run the script at a desired interval. For example, to run the script every Sunday at 3:00 AM:

1.  Open your crontab for editing:
    ```bash
    crontab -e
    ```
2.  Add the following line, making sure to replace `/path/to/project` with the absolute path to the `SmartCFDTradingAgent_Revolut` directory:

    ```cron
    0 3 * * 0 /usr/bin/python3 /path/to/project/scripts/retrain_model.py >> /path/to/project/logs/retraining.log 2>&1
    ```

This command will execute the script and append its output (both stdout and stderr) to a log file for later review.

#### Windows Task Scheduler

1.  Open **Task Scheduler** and select **Create Basic Task...**.
2.  **Name:** Give the task a descriptive name, like "Weekly Model Retraining".
3.  **Trigger:** Choose a schedule, such as **Weekly**, and select a day and time (e.g., Sunday at 3:00 AM).
4.  **Action:** Select **Start a program**.
5.  **Program/script:** Enter the full path to your Python executable (e.g., `C:\Python311\python.exe`).
6.  **Add arguments (optional):** Enter the full path to the script: `C:\Projects\SmartCFDTradingAgent_Revolut\scripts\retrain_model.py`.
7.  **Start in (optional):** Enter the project's root directory: `C:\Projects\SmartCFDTradingAgent_Revolut`. This ensures the script can correctly locate project files.
8.  **Finish:** Complete the wizard. You may want to open the task's properties to configure it to "Run whether user is logged on or not".

This completes the implementation of the automated retraining workflow, a key component of the V1.0 system.
````
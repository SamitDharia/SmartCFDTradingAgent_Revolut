# Windows Task Scheduler for Docker

This guide walks through scheduling the trading agent on Windows using Task Scheduler with Docker Compose.

## Steps
1. Open **Task Scheduler** and choose **Create Basic Task...**.
2. Pick a trigger suitable for your run cadence (e.g., daily or at logon).
3. In **Action**, select **Start a Program**.
4. Set **Program/script** to `docker-compose` and **Add arguments** to:
   ```
   up -d
   ```
5. Set **Start in** to the project root directory (e.g., `C:\Projects\SmartCFDTradingAgent_Revolut`). This is crucial so Docker Compose can find the `docker-compose.yml` and `.env` files.
6. Finish the wizard. Ensure the task runs under an account with permissions to run Docker.

This setup will start the trading agent in a detached container. To stop it, you can create another task with the arguments `down`.

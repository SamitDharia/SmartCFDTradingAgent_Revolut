# Windows Task Scheduler

This guide walks through scheduling the trading agent on Windows using Task Scheduler.

## Steps
1. Open **Task Scheduler** and choose **Create Basic Task...**.
2. Pick a trigger suitable for your run cadence (e.g., daily or at logon).
3. In **Action**, select **Start a Program**.
4. Set **Program/script** to `cmd` and **Add arguments** to:
   ```
   /c "set TELEGRAM_BOT_TOKEN=123456:ABC-XYZ && set TELEGRAM_CHAT_ID=123456789 && python -m SmartCFDTradingAgent.pipeline --config configs/crypto.yml --profile crypto_1h"
   ```
5. Set **Start in** to the project root so the `.env` file is found.
6. Finish the wizard. Ensure the task runs under an account with network access and the necessary permissions.

The `set` commands assign environment variables for the single run before launching Python. Edit the command, paths, and schedule as needed.

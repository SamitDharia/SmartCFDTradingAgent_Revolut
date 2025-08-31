# Linux Cron Scheduling

Use `cron` to run the trading agent automatically on Unix-like systems.

## Example
Edit your crontab:
```bash
crontab -e
```
Add an entry to run the market loop at 14:30 UTC every weekday:
```cron
30 14 * * 1-5 /path/to/SmartCFDTradingAgent_Revolut/scripts/market_loop.sh >> /path/to/market_loop.log 2>&1
```
The entry changes to the project directory, loads the `.env` file, and runs the helper script. Customize paths, schedule, and command options for your environment.

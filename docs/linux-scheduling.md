# Linux Cron Scheduling for Docker

Use `cron` to run the trading agent automatically on Unix-like systems using Docker Compose.

## Example
Edit your crontab:
```bash
crontab -e
```
Add an entry to start the Docker container at a specific time, for example, at 08:00 UTC every day:
```cron
0 8 * * * cd /path/to/SmartCFDTradingAgent_Revolut && docker-compose up -d >> /path/to/cron.log 2>&1
```
This `cron` job will change to the project directory and start the services defined in `docker-compose.yml` in detached mode. Logs will be managed by Docker.

To stop the service, you can set up another cron job:
```cron
0 18 * * * cd /path/to/SmartCFDTradingAgent_Revolut && docker-compose down >> /path/to/cron.log 2>&1
```
Customize the paths and schedule to fit your needs.

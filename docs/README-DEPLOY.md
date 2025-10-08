# Deploying the V1.0 Trading Agent

This document provides the official, simplified instructions for building and running the V1.0 trading agent using Docker Compose. The agent is designed to run as a persistent, long-running service.

## One-Time Setup
1.  **Copy Configuration**: If you haven't already, copy the main configuration file. You do not need a separate deploy-time config file.
    ```bash
    cp config.ini.example config.ini
    ```
2.  **Edit Configuration**: Open `config.ini` and fill in your `API_KEY` and `API_SECRET` under the `[alpaca]` section. Ensure `ALPACA_ENV` is set to `paper` for paper trading or `live` for real money.

## Running the Agent

1.  **Build the Docker Image**:
    ```bash
    docker compose build
    ```
2.  **Run as a Detached Service**:
    ```bash
    docker compose up -d
    ```
    This command starts the `app` service in the background and will automatically restart it unless it is explicitly stopped.

3.  **View Logs**: To monitor the agent's activity in real-time, use the logs command:
    ```bash
    docker compose logs -f
    ```
    *(Note: The service name is `app`, not `smartcfd-agent`)*

## How It Works

The `docker compose up -d` command starts the service defined in `docker-compose.yml`. The container runs the `docker/runner.py` script, which contains the main application loop. This loop periodically executes the trading logic based on the `run_interval_seconds` setting in `config.ini`.

The agent's health can be monitored via the built-in health check, which ensures the application remains responsive and connected to its database. You can inspect the container's state with `docker ps`.

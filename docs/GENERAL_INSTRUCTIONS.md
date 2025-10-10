# General Project Instructions & Vision

**Mission:**  
To build a fully autonomous, intelligent trading system. The agent will leverage machine learning to make data-driven decisions, manage risk, and operate independently in live paper trading environments.

---

## 🧭 Core Project Documents

This project is guided by a set of living documents that track our progress, plans, and learnings. These are the primary sources of truth for our work:

1.  **[Project Summary (`PROJECT_SUMMARY.md`)](PROJECT_SUMMARY.md)**
    *   **Purpose:** A high-level overview of the project, its objectives, and key achievements. Suitable for resumes and external showcases.
    *   **Content:** Defines the project's goals, technologies, and clearly outlines our respective roles.

2.  **[Development Roadmap (`ROADMAP.md`)](ROADMAP.md)**
    *   **Purpose:** The strategic plan outlining all development phases, from initial setup to future features for Version 2.0.
    *   **Content:** Contains a detailed, phase-by-phase breakdown of tasks. We follow this roadmap to guide our development priorities.

3.  **[Lessons Learned (`LESSONS_LEARNED.md`)](LESSONS_LEARNED.md)**
    *   **Purpose:** A project retrospective and journal.
    *   **Content:** We continuously update this document with key learnings, mistakes, and important decisions made during the development of V1.0.

4.  **[SWOT Analysis (`SWOT_ANALYSIS.md`)](SWOT_ANALYSIS.md)**
    *   **Purpose:** A strategic analysis of the project's internal strengths/weaknesses and external opportunities/threats.
    *   **Content:** Informs the strategic direction and helps prioritize tasks on the roadmap.

---

##  VISION

### 🧠 Machine Learning & Strategy Engine (Version 1.0)
The core of this project is an adaptive strategy engine. The system:
-   Uses an XGBoost model to generate predictions based on technical indicators.
-   Incorporates robust risk management, including dynamic stop-losses and take-profits.
-   Adapts to market conditions using a market regime detector.

### ✨ Future Ambitions (Version 2.0)
-   **Advanced Monitoring:** A sleek, modern, and interactive dashboard (e.g., using Streamlit) to visualize the bot's performance and operations in real-time.
-   **Portfolio Optimization:** Evolve from single-asset trading to true portfolio management using Modern Portfolio Theory (MPT).
-   **Alternative Data:** Integrate non-price-based data sources (e.g., news sentiment, on-chain metrics) to create a richer feature set.

---

## ⚙️ Running the Bot: Environment & Networking

For the trading bot to operate correctly, the following conditions must be met:

1.  **Docker:** The application is containerized with Docker and managed with `docker-compose`. Ensure Docker Desktop is running on your system.
2.  **Configuration:** A valid `config.ini` file with the correct Alpaca API keys must be present in the root directory.
3.  **Network Connection:** The bot requires a direct, unfiltered internet connection to communicate with the Alpaca API.
    *   **VPNs:** Corporate or private VPNs will likely cause `SSL certificate verification` errors and must be **turned off**.
    *   **Restrictive Networks:** Some corporate or public WiFi networks may block the necessary connections. If you encounter persistent network issues, switch to a less restrictive network (e.g., a mobile hotspot).

To start the bot in detached mode (runs in the background):
```bash
docker-compose up --build -d
```

To start the bot and view live logs in the terminal:
```bash
docker-compose up --build
```

To view the logs of a running container:
```bash
docker-compose logs --tail 100 -f
```

### Core Development Principle: Verify, Don't Assume

A critical lesson learned during the development of V1.0 was the importance of verification over assumption. Multiple errors and significant delays were caused by assuming the location or behavior of code elements.

**Before writing code that depends on another part of the project, always:**

1.  **Verify Existence**: Use a workspace search to confirm that the variable, function, or class you need actually exists.
2.  **Verify Location**: Once you know it exists, confirm the correct file and module path.
3.  **Verify Signature**: Check the function/method signature to ensure you are passing the correct arguments.

This simple, disciplined process prevents `ImportError` and `AttributeError` issues and is much faster than debugging after a failed assumption. For a detailed history of these issues, see the `LESSONS_LEARNED.md` file.

---

## ⚙️ Running the Bot: A Step-by-Step Guide

This guide provides the exact steps to get the trading bot running in a clean, reliable Docker environment.

### Prerequisites

1.  **Docker Desktop:** Ensure Docker Desktop is installed and the Docker daemon is running.
2.  **API Keys:** You must have a valid `config.ini` file in the project root, populated with your Alpaca API key and secret. Create it from `config.ini.example` if it doesn't exist.

### Step 1: Build and Start the Containers

The application is managed using `docker-compose`. To build the Docker images and start the services in detached mode (running in the background), use the following command:

```bash
docker-compose up --build -d
```

*   `--build`: This flag forces Docker to rebuild the images, ensuring any code changes are included.
*   `-d`: This flag runs the containers in detached mode.

### Step 2: Monitor the Application Logs

To view the live logs from the main application container (`app`), use:

```bash
docker-compose logs -f app
```

*   `-f`: "Follows" the log output, showing new logs in real-time.
*   `app`: This is the name of the service defined in `docker-compose.yml`.

You should see output indicating that the runner has started, the portfolio has been reconciled, and the strategy is being evaluated.

### Step 3: Check Application Health

The application exposes a health check endpoint. You can verify that the system is healthy by accessing it in your browser or using a tool like `curl`:

```bash
# From your local machine's terminal
curl http://localhost:8080/healthz
```

A healthy application will return:
```json
{"status": "ok"}
```

An unhealthy application will return a `503` status code with details about the failure.

### Step 4: Stopping the Application

To stop the running containers, use:

```bash
docker-compose down
```

This will stop and remove the containers and the network created by `docker-compose up`.

### Troubleshooting Common Issues

*   **`longintrepr.h: No such file or directory` on build:** This indicates a missing Python development environment. The `Dockerfile` has been fixed to include the necessary build tools, so a fresh build (`docker-compose up --build`) should resolve this.
*   **`401 Unauthorized` or `404 Not Found` from Alpaca:**
    1.  Double-check that your API key and secret in `config.ini` are correct.
    2.  Ensure `alpaca_env` is set correctly (e.g., `paper`).
    3.  The `alpaca-trade-api` library has been upgraded to `3.2.0` to use the correct modern endpoints.
*   **`AttributeError` or `TypeError` related to Pandas:** These were common during development due to inconsistent timezone handling. The codebase has been standardized to use timezone-aware UTC timestamps. If new errors of this type appear, the first step is to inspect the DataFrame's index (`df.index`) to ensure it is a `pd.DatetimeIndex` and is timezone-aware.
*   **Health Check Failures (`503` status):** The health check now correctly receives all necessary configuration. If it fails, check the application logs (`docker-compose logs -f app`) for specific error messages related to `health.compute.data_feed_fail` or `health.compute.db_fail`.

---

This document serves as the central hub. For specifics on **what we are doing next**, always refer to the **[Development Roadmap](ROADMAP.md)**.

---

## End-to-End Trade Validation (BTC/USD)

1. Ensure `watch_list=BTC/USD` and set a sensible `trade_confidence_threshold` in `config.ini` (e.g., 0.7–0.9).
2. Start the app and tail logs: `docker-compose up --build` or `docker-compose logs -f`.
3. Look for `trader.initiate_trade.success` with both broker `entry_order_id` and stored `client_order_id`.
4. On entry fill, expect `trader.arm_exits.success` logging TP/SL client IDs.
5. When one exit fills, expect `reconcile_trade_groups.closed_tp` or `closed_sl`, and confirm the peer order was cancelled.

## Tips: Efficient AI/Prompt Usage

- Request “apply_patch only” responses targeting a single file/function.
- Keep a short repo map and reference functions by path and name.
- Use selection-based prompting in your IDE for local refactors.
- Split changes into small, verifiable steps (entry → arm exits → OCO → reconcile).

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

This document serves as the central hub. For specifics on **what we are doing next**, always refer to the **[Development Roadmap](ROADMAP.md)**.

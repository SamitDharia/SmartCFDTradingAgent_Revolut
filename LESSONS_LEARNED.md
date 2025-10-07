# Project Learnings & Retrospective

This document tracks the key learnings, mistakes, and pivotal decisions made throughout the development of the Smart CFD Trading Agent. It serves as a living journal to reflect on the development process and improve future work.

## Section 1: Environment & Setup

*   **Mistake:** Underestimating the complexity of setting up a consistent Docker environment on Windows. We spent significant time troubleshooting issues related to WSL (Windows Subsystem for Linux), Docker Desktop daemon connectivity, and file permissions.
*   **Mistake:** `CRLF` vs `LF` line endings. The `entrypoint.sh` script failed silently inside the container because of Windows-style `CRLF` line endings. This was a subtle but critical bug that was hard to diagnose from the Docker logs alone.
*   **Learning:** A stable and reproducible development environment is paramount. Debugging environment issues is often harder than debugging code. We learned to systematically check for common cross-platform problems (like line endings) early in the process.
*   **What We Could Do Differently:** We could have started with a simpler, non-containerized setup to develop the core Python logic first. Once the application was proven to work locally, we could have then focused on containerizing it. This would have separated application debugging from environment debugging.

## Section 2: Configuration & API Integration

*   **Mistake:** Using incorrect environment variable names for the Alpaca API (`ALPACA_API_KEY` instead of the correct `APCA_API_KEY_ID`). This led to a `401 Unauthorized` error.
*   **Learning:** A `401` error is almost always an authentication issue. The first step should be to meticulously verify API keys, secrets, and the exact variable names the client library expects.
*   **Learning:** The importance of a `config.py` module to centralize all configuration. When we encountered an `AttributeError` because `run_interval_seconds` was missing, adding it to the central config was a clean and easy fix.

## Section 3: ML Model Deployment & Debugging

*   **Mistake:** The initial `InferenceStrategy` implementation incorrectly tried to call `get_bars` on the `AlpacaClient` object, which was a method on the `AlpacaBroker`. This revealed a flaw in the dependency injection and separation of concerns.
*   **Mistake (AI Agent):** During the fix, I (the AI agent) got into a temporary loop by trying to patch a solution that introduced new errors, rather than stepping back to address the root cause.
*   **Learning:** User intervention was critical to break the debugging loop. It highlighted the importance of re-evaluating the core problem when a fix becomes overly complicated. The correct solution was simpler: use the `DataLoader` to fetch data within the strategy, respecting the established architecture.
*   **Learning:** The `FutureWarning` from the `ta` library is a good reminder to keep dependencies in mind and plan for future updates or refactoring to avoid breaking changes.

## Section 4: Strategic Decisions & Project Management

*   **Pivotal Moment:** The decision to prioritize "Robustness & Safety Mechanisms" in the roadmap. This was a strategic shift from focusing purely on entry signals to building a more complete, production-ready system with risk management at its core.
*   **Learning:** It's crucial to understand the full lifecycle of a trade (entry, management, exit). We realized that an entry-only strategy is incomplete and carries significant risk, prompting the immediate focus on implementing stop-loss and take-profit logic.
*   **Good Practice:** Creating the `PROJECT_SUMMARY.md` and this `LESSONS_LEARNED.md` document. This helps formalize the project's progress and learnings, which is invaluable for portfolio building and future reference.

*(This document will be updated as the project progresses.)*

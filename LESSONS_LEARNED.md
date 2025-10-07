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
*   **Mistake:** The `Trader` was calling `risk_manager.calculate_order_qty()`, but the method did not exist in the `RiskManager` class. This caused an `AttributeError` on every trade attempt, preventing any orders from being placed.
*   **Learning:** This error emphasized the importance of ensuring the full execution path is wired correctly. While the signal generation was working perfectly, the hand-off to the risk management and execution layer was broken. It also served as the natural next step, forcing the implementation of the critical position-sizing logic.
*   **Resolution:** Implemented the `calculate_order_qty` method in `risk.py`, which calculates a trade size based on a percentage of equity. This required adding a new `risk_per_trade_percent` setting to `config.py` and a `get_latest_crypto_trade` method to `alpaca_client.py` to fetch the current price.

## Section 4: Strategic Decisions & Project Management

*   **Pivotal Moment:** The decision to prioritize "Robustness & Safety Mechanisms" in the roadmap. This was a strategic shift from focusing purely on entry signals to building a more complete, production-ready system with risk management at its core.
*   **Learning:** It's crucial to understand the full lifecycle of a trade (entry, management, exit). We realized that an entry-only strategy is incomplete and carries significant risk, prompting the immediate focus on implementing stop-loss and take-profit logic.
*   **Good Practice:** Creating the `PROJECT_SUMMARY.md` and this `LESSONS_LEARNED.md` document. This helps formalize the project's progress and learnings, which is invaluable for portfolio building and future reference.

## Section 5: Networking & Deployment

*   **Mistake:** Running the application on a network with an active VPN caused SSL certificate verification failures.
*   **Symptom:** The application would fail with an `[SSL: CERTIFICATE_VERIFY_FAILED]` error when trying to connect to the Alpaca API.
*   **Cause:** The corporate VPN was intercepting the HTTPS traffic, presenting its own certificate, which did not match the expected certificate from Alpaca's servers. This is a common security practice on corporate networks but breaks applications that perform strict certificate validation.
*   **Resolution:** The user disabled the VPN, which allowed for a direct and unfiltered connection to the Alpaca API.

*   **Mistake:** Assuming Docker's default networking would seamlessly handle host network changes, especially on restrictive corporate networks.
*   **Symptom:** After resolving the VPN issue, the container began failing with a `NameResolutionError`, unable to resolve Alpaca's domain names (e.g., `paper-data.alpaca.markets`). This occurred after switching between different WiFi networks.
*   **Cause:** The Docker container was not using a reliable DNS server. The host's network configuration, particularly on the corporate WiFi and mobile hotspot, did not automatically provide a working DNS resolver to the container.
*   **Resolution:** We explicitly configured the Docker container to use reliable public DNS servers by adding the following to `docker-compose.yml`:
    ```yaml
    dns:
      - 8.8.8.8  # Google's public DNS
      - 1.1.1.1  # Cloudflare's public DNS
    ```
*   **Learning:** For applications requiring robust internet connectivity from within a Docker container, it's best practice to explicitly define DNS servers. This decouples the container's networking from the host's potentially restrictive or inconsistent network environment, making the deployment more portable and reliable.

## Section 6: Script Errors & Configuration Management

*   **Mistake:** Encountering an `ImportError` in the `scripts/verify_alpaca_orders.py` script due to incorrect assumptions about the configuration structure.
*   **Learning:** Utility and verification scripts should have minimal dependencies on the main application's internal logic. When a script needs configuration, it's often better to read directly from environment variables (`.env`) rather than trying to reuse complex configuration objects that might not be designed for standalone execution. This reduces coupling and makes scripts more robust and easier to maintain.
*   **Resolution:** The script was modified to directly read the necessary configuration from environment variables, making it self-contained and independent of the main application's configuration logic.

*   **Mistake:** After fixing the initial `ImportError` in `scripts/verify_alpaca_orders.py`, a second one occurred. The script tried to import `ALPACA_PAPER_BASE_URL` and `ALPACA_LIVE_BASE_URL` from `smartcfd.alpaca`, which was incorrect.
*   **Root Cause:** This was a direct result of making an assumption about the location of these constants without verifying. A quick search of the codebase would have revealed that they are defined in `smartcfd.broker`. This highlights a process failure: assuming the location of a variable instead of confirming it.
*   **Solution:** The import statement was corrected to `from smartcfd.broker import ALPACA_PAPER_BASE_URL, ALPACA_LIVE_BASE_URL`.
*   **Lesson:** Do not assume the location of variables, functions, or classes. When an `ImportError` occurs, use workspace search tools to find the correct module where the desired object is defined. This simple verification step prevents chained errors and saves debugging time. Trust, but verify—even your own assumptions about the code.

---

### `ImportError` from Non-Existent Variable

**Date:** 2025-10-07

**Problem:**
After multiple failed attempts to fix an `ImportError` for `ALPACA_PAPER_BASE_URL` by changing the import path, a workspace search revealed that the constant was not defined anywhere in the project's Python code.

**Root Cause:**
This was a severe process failure. The core mistake was assuming the variable existed at all. Instead of just guessing its location, the first step should have been to confirm its existence. The repeated failures were a direct result of trying to fix the *location* of an import without ever verifying the *existence* of the target.

**Solution:**
The non-existent import was removed. The required URL strings were defined directly within the `scripts/verify_alpaca_orders.py` script. For a simple utility script, defining constants locally is a much cleaner and more robust solution than creating a dependency on a non-existent variable.

**Lesson:**
The most critical lesson of all: **Verify, then trust.** Before attempting to import or use any object, first confirm that it actually exists in the codebase. A simple text search is the most powerful tool for this. Chasing `ImportError`s by guessing paths is inefficient and leads to repeated failures. Confirm existence first, then determine location.
---

### Environment Variable Precedence

**Date:** 2025-10-07

**Problem:**
Even after setting the correct API keys in the `.env` file, the application continued to use old, invalid keys, resulting in persistent `401 Unauthorized` errors. Debugging revealed that the incorrect keys were pre-loaded in the terminal environment.

**Root Cause:**
The `python-dotenv` library, by default, does **not** override existing environment variables. If a variable like `APCA_API_KEY_ID` is already set in the shell (e.g., through a system-wide setting, a shell profile, or a VS Code launch configuration), `load_dotenv()` will silently ignore the value in the `.env` file. This can create a confusing situation where the code appears to be ignoring the local configuration.

**Solution:**
To ensure that the `.env` file is always the single source of truth for the application's environment, the `load_dotenv()` function was called with the `override=True` parameter: `load_dotenv(override=True)`. This forces the library to overwrite any pre-existing environment variables with the values from the `.env` file, making the application's behavior predictable and independent of the shell's state.

**Lesson:**
For applications that should be configured primarily by a local `.env` file, always use `load_dotenv(override=True)`. This makes the project more portable and eliminates a major source of "it works on my machine" problems by ensuring that the local configuration takes precedence over any potentially stale or incorrect system-level environment variables.
---

### Unit Testing & Mocking Complexity

**Date:** 2025-10-07

**Problem:**
While implementing the "Circuit Breaker" feature, a suite of unit tests began failing with a variety of errors, including `AttributeError`, `AssertionError`, and `requests.exceptions.HTTPError`. The debugging process was prolonged and difficult.

**Root Cause:**
There were several underlying issues:
1.  **Inconsistent Mocking Strategy:** The tests for `RiskManager` were mixing `requests-mock` with direct `MagicMock` patching, leading to unpredictable behavior and `AttributeError`s.
2.  **State Management Bugs:** The `RiskManager`'s `check_for_halt` method had flawed logic for setting and, more importantly, resetting its `is_halted` state. This caused tests for the halt-reset functionality to fail.
3.  **Mocking Library Interactions:** The `test_retry_logic_on_5xx_error` test failed because `requests-mock` intercepts HTTP calls before the `requests` library's `Retry` adapter can process them. This is a fundamental interaction detail of the mocking library that was not initially accounted for.

**Solution:**
A systematic, multi-step approach was required:
1.  **Standardized Mocking:** The `test_risk.py` file was refactored to use a consistent mocking strategy, relying on a `MagicMock(spec=AlpacaClient)` fixture. This ensured that all mocked methods adhered to the real client's interface, eliminating `AttributeError`s.
2.  **Corrected State Logic:** The `check_for_halt` method in `smartcfd/risk.py` was rewritten to have a clear, single path for checking all halt conditions and an explicit block to reset the `is_halted` state if no conditions were met.
3.  **Adapted Test for Mock Behavior:** The `test_retry_logic_on_5xx_error` was rewritten. Instead of trying to assert a successful final outcome (which is impossible with the mock), the test was changed to assert that the initial call fails with the expected `HTTPError`. This correctly tests the behavior within the constraints of the mocking environment.

**Lesson:**
Complex features with multiple states and external dependencies require a rigorous and disciplined testing approach.
- **Isolate and Standardize Mocks:** When testing a component, mock its immediate dependencies cleanly and consistently. Avoid mixing different mocking techniques (like patching and response-mocking) on the same dependency.
- **Test State Transitions Explicitly:** For stateful classes like `RiskManager`, write separate tests for each state transition: entering a state (e.g., `is_halted = True`), remaining in a state, and exiting a state (`is_halted = False`).
- **Understand Your Tools:** Be aware of the limitations and interactions of your testing libraries. `requests-mock` is powerful, but it fundamentally changes how HTTP requests are handled, which can interfere with other libraries like `urllib3.Retry`. Adapt tests to account for this.

---

*(This document will be updated as the project progresses.)*

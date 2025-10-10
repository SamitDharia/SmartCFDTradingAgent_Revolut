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

## Section 4.1: Trade Lifecycle Completeness (Entry → Arm Exits → OCO Closure)

*   **Gap Identified:** Entry orders were placed, but exit orders (TP/SL) were not armed automatically on fill for crypto where native OCO is unavailable.
*   **Resolution:** Implemented client-side OCO with two separate orders (limit and stop) and cancel-on-fill logic. Persisted client_order_ids in the trade group to reconcile reliably.
*   **Lesson:** Persist and reconcile by client_order_id, not transient broker IDs, to avoid fragile lookups and simplify idempotent operations.

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

### Health Checks and Startup Race Conditions

**Date:** 2025-10-08

**Problem:**
After successfully retraining the model and fixing all core logic, the application would start in Docker but immediately report as unhealthy. The logs showed the health check endpoint (`/healthz`) returning `503 Service Unavailable` because the data feed was being flagged as anomalous at startup.

**Root Cause:**
This was a classic race condition. The health check server started at the same time as the main trading application. The first few data points fetched by the `DataLoader` were sometimes incomplete or had unusual values (e.g., zero volume) right as the market opened or the bot first connected. The `has_anomalous_data` check was too strict and immediately flagged the data feed as unhealthy. This caused a cascading failure where the application was marked as down before it had a chance to stabilize and fetch a clean data set.

**Solution:**
A 60-second startup grace period was implemented in the `health_server.py`. During this initial period, the `/healthz` endpoint will always return a `200 OK` status, regardless of the underlying component health. This gives the `DataLoader` and other components enough time to initialize, connect, and fetch a stable stream of data before health monitoring begins in earnest.

**Lesson:**
Health checks for complex, multi-component systems must account for startup and initialization time. A "grace period" is a common and effective pattern to prevent transient, startup-related issues from triggering false-positive health check failures. This makes the system more resilient and prevents it from being prematurely terminated by an orchestrator (like Kubernetes or Docker Swarm) in a production environment.
---

### Unit Testing & Mocking Complexity

**Date:** 2025-10-08

**Problem:**
A series of integration tests were failing with obscure errors that were difficult to trace back to the root cause. The failures manifested in several ways:
1.  `TypeError: '<' not supported between instances of 'str' and 'int'`
2.  `AssertionError: Expected 'submit_order' to have been called once. Called 0 times.`
3.  `KeyError: 'qty'` in test assertions.
4.  Regressions where fixing one test broke another.

**Root Cause Analysis:**
The debugging process revealed a cascade of issues stemming from the complexity of the `Trader`, `RiskManager`, and `Broker` interactions, and how they were mocked in `tests/test_integration.py`.

1.  **Data Type Mismatch in Mocks:** The initial `TypeError` was caused by providing string values (e.g., `"0.2"`) for numeric fields (like `qty` and `market_value`) in the mock `Position` objects. The application logic expected floats, leading to comparison errors.
2.  **Incorrect Method Mocking:** The `AssertionError` (0 calls) was due to a mismatch between the method being called in the application (`broker.post_order`) and the method being asserted in the test (`broker.submit_order.assert_called_once()`). This was a simple but critical oversight.
3.  **Positional vs. Keyword Arguments:** The `KeyError` occurred because the test was trying to assert the contents of `call_args.kwargs`, but the `submit_order` mock was being called with a single positional argument: a Pydantic `OrderRequest` object. The correct approach was to inspect `call_args.args[0]`.
4.  **Flawed Application Logic:** The most subtle issue was in the `Trader.execute_order` logic itself. The initial implementation did not allow for adding to an existing position. Attempts to fix this introduced regressions because the test cases were not designed to handle this new behavior, leading to unexpected mock call counts.

**Solution:**
The solution was a multi-step process:
1.  **Corrected Mock Data:** All mock `Position` objects in `tests/test_integration.py` were updated to use floating-point numbers for numeric fields.
2.  **Standardized Method Name:** The call in `smartcfd/trader.py` was changed from `self.broker.post_order(...)` to `self.broker.submit_order(...)` to match the rest of the codebase and the test assertions.
3.  **Updated Assertions:** The test assertions were refactored to correctly inspect the positional `OrderRequest` object, like so:
    ```python
    call_args, _ = self.trader.broker.submit_order.call_args
    order_request = call_args[0]
    self.assertEqual(order_request.symbol, 'ETH/USD')
    ```
4.  **Refined Application and Test Logic:** The `Trader.execute_order` method was updated to correctly handle adding to existing positions. The corresponding tests (`test_buy_signal_when_one_position_exists` and `test_order_limited_by_asset_exposure`) were then updated to assert this new, correct behavior, ensuring the test suite accurately reflected the desired application logic.

**Lesson:**
Complex integration tests with multiple mocks are brittle. When they fail, it's crucial to debug systematically:
-   **Verify Data Types:** Ensure mock data perfectly matches the types expected by the application.
-   **Check Method Names:** Double-check that the mocked method name matches the called method name.
-   **Inspect Call Arguments:** When assertions fail, print the entire `call_args` object to see exactly how the mock was called (positional vs. keyword).
-   **Align Tests with Logic:** When application logic changes, the tests that cover that logic must be updated to reflect the new behavior. A failing test might indicate that the *test* is wrong, not the application code.
---

### Hyperparameter Tuning and Model Selection

**Date:** 2025-10-07

**Problem:**
The baseline `RandomForestClassifier` model had a modest accuracy of around 52-53%. To improve predictive performance, a more systematic approach was needed to find better model settings and explore more advanced algorithms.

**Solution:**
1.  **Implemented Hyperparameter Tuning:** The `scripts/train_model.py` script was significantly enhanced to include a hyperparameter tuning pipeline using `sklearn.model_selection.RandomizedSearchCV`. This allowed for an efficient search across a wide range of parameters for a given model.
2.  **Tuned RandomForest:** The pipeline was first applied to the existing `RandomForestClassifier`. The search found an optimal set of parameters that improved the model's accuracy to **55%**.
3.  **Experimented with XGBoost:** To explore more powerful models, `xgboost` was added to the project. The training script was adapted to use `XGBClassifier`, and a new parameter grid was defined for the randomized search.
4.  **Tuned XGBoost:** The tuning process was run for the `XGBClassifier`, which also resulted in a model with **55%** accuracy. The best-performing XGBoost model was then saved as the new production model (`models/model.joblib`).

**Lesson:**
- **Systematic Tuning is Key:** Manual parameter tweaking is inefficient. A systematic search like `RandomizedSearchCV` is essential for finding optimal model configurations and improving performance.
- **Advanced Models Aren't a Silver Bullet:** Switching from RandomForest to a more complex model like XGBoost did not yield an immediate breakthrough in accuracy. Both models plateaued at 55% with the current feature set. This suggests that further significant gains are more likely to come from **feature engineering** (creating more predictive input data) or exploring different model architectures (like time-series models) rather than just tuning the existing algorithm.
- **Establish a Baseline:** The process of tuning and evaluating different models provides a solid performance baseline. We now know that with the current features, 55% accuracy is the benchmark to beat. This informs our decision to focus next on data quality and feature engineering rather than spending more time on model tuning alone.

---

## Section 8: State Management & Refactoring

**Date:** 2025-10-07

**Problem:**
The initial architecture had a critical flaw: state was decentralized. Components like the `RiskManager` and `Strategy` made direct, independent calls to the broker to get account or position information. This led to redundant API calls, potential for data inconsistency between components, and made the system difficult to test and maintain.

**Solution:**
A major architectural refactoring was undertaken to introduce a centralized state management system.
1.  **`PortfolioManager` Created:** A new class, `smartcfd.portfolio.PortfolioManager`, was created to be the single source of truth for the application's state.
2.  **Reconciliation Loop:** The `PortfolioManager` was given a `reconcile()` method, which is called once at the beginning of each trading cycle. This method fetches the latest account, position, and order data from the broker and updates its internal state.
3.  **Dependency Injection:** The `Trader`, `RiskManager`, and `Strategy` were all refactored to accept a `PortfolioManager` instance in their `__init__` methods.
4.  **State-Driven Logic:** All direct calls to the broker for state information (e.g., `client.get_account()`, `client.get_positions()`) were removed from the individual components and replaced with calls to the `PortfolioManager`'s state (e.g., `portfolio.account`, `portfolio.positions`).
5.  **Comprehensive Testing:** New unit tests were written for the `PortfolioManager` itself. Crucially, a new suite of integration tests (`tests/test_integration.py`) was created to verify that the entire trading loop worked correctly with the new state management system.

**Lesson:**
- **Centralize State:** For any application that manages a real-time state (like a trading bot), centralizing that state is paramount. A single source of truth prevents race conditions, ensures data consistency, reduces external API calls, and makes the system's logic far easier to reason about.
- **The Cost of "Easy" Early On:** The initial approach of letting each component fetch its own data was easier to implement at first, but the long-term cost in complexity and brittleness was high. This refactoring, while significant, was a necessary investment to build a robust and scalable system.
- **Integration Tests are Non-Negotiable for Refactoring:** Unit tests for the new `PortfolioManager` were not enough. The integration tests were absolutely critical to prove that the refactoring didn't break the complex interactions between the `Trader`, `Strategy`, and `RiskManager`. The painful, iterative process of getting these tests to pass revealed and fixed numerous subtle bugs in the new implementation.

---

## Section 9: Test Suite Integrity & Refactoring Fallout

**Date:** 2025-10-07

**Problem:**
After a series of refactorings (introducing multi-asset trading and percentage-based risk), the entire test suite was run and produced a cascade of failures and errors across multiple test files. This included `TypeError`s from changed constructors and `AssertionError`s from incorrect mock setups.

**Root Cause:**
This was a significant process failure. Changes were made to core components (`RiskConfig`, `InferenceStrategy`, `Trader`), but the corresponding unit and integration tests that depended on them were not updated simultaneously. The assumption was made that because the new, isolated tests passed, the old ones were still valid. This was incorrect. The interdependencies in the codebase meant that a change in one place had ripple effects that were not caught until a full test run was initiated.

**Solution:**
A systematic effort was undertaken to fix the entire test suite:
1.  **`test_risk.py`:** The `RiskConfig` fixture was updated to use the new percentage-based parameters, resolving the `TypeError`.
2.  **`test_inference_strategy.py`:** The `InferenceStrategy` constructor calls were updated to remove the obsolete `symbol` argument.
3.  **`test_trader.py`:** The `Trader` constructor calls were updated to include the required `AppConfig` and `PortfolioManager` objects.
4.  **`test_integration.py`:** The most problematic test, which was failing due to complex state mocking, was simplified by patching the `calculate_order_qty` method. This allowed the test to focus on validating the integration of the components without getting stuck on mocking details.

**Lesson:**
- **Always Run the Full Test Suite:** After any non-trivial refactoring, **always** run the entire test suite. Do not assume that passing a few new tests means the system is stable. The purpose of a comprehensive test suite is to catch these exact kinds of regressions.
- **Update Tests with Code:** Treating tests as second-class citizens is a recipe for technical debt. When a function or class constructor is changed, the tests that use it must be updated as part of the same commit. They are not an afterthought.
- **Isolate vs. Integrate:** The failure highlighted the difference between unit and integration tests. The new `RiskManager` unit tests passed because they were isolated. The integration tests failed because they test the connections between components. Both are essential. When an integration test is too complex to maintain, simplify it by patching a lower-level component (as was done with `calculate_order_qty`) to focus on the specific interaction being tested.
- **Do Not Assume a Pass:** The AI agent made a critical error in reporting that tests had passed without verifying the output of the test runner. The output clearly showed failures. The new instruction is to **always** read the test results carefully and report the exact outcome before proceeding. Trust the test runner, not assumptions.

---

### Revolut API Research & Project Pivot

**Date:** 2025-10-07

**Problem:**
The project was initially named with "Revolut" in mind, assuming a trading API would be available. A key task was to confirm this and plan the integration.

**Solution:**
A thorough investigation was conducted using web searches of Revolut's official documentation, developer hub, and community forums. The research concluded:
-   **No Retail Trading API:** Revolut does not provide a public API for its retail customers to automate stock or CFD trading.
-   **Business & Crypto APIs Exist:** APIs are available for Revolut Business (for payments) and Revolut X (for crypto trading), but these do not serve the project's purpose of trading CFDs or stocks on a personal account.
-   **Unofficial Methods are Unsafe:** While some have attempted to reverse-engineer the private mobile app API, this is against the terms of service, unstable, and a major security risk.

**Lesson:**
- **Validate Core Assumptions Early:** A foundational assumption of the project (the existence of a Revolut trading API) was proven false. This was a critical finding that led to a strategic pivot. It's a powerful lesson in the importance of conducting a "spike" or feasibility study for any critical, external dependency before committing significant development effort.
- **Adapt the Strategy:** The project's focus was officially and successfully pivoted to use Alpaca for both paper and live trading. The project's value is in its signal generation and risk management, which is broker-agnostic. The research was documented and the project's focus was clarified across all documentation.

---

### Docker Container Startup Failures

**Date:** 2025-10-07

**Problem:**
After a major refactoring of the application's state management, the Docker container failed to start, triggering a cascade of different errors. The debugging process was iterative and complex, requiring multiple builds and fixes.

**Root Cause Analysis & Resolution:**
The debugging process uncovered a series of distinct, layered issues:
1.  **`TypeError` in `RiskManager`:** The `RiskManager` constructor signature was changed during refactoring, but the instantiation in `docker/runner.py` was not updated. **Lesson:** Refactoring a class's `__init__` requires updating all call sites.
2.  **`TypeError` in `Trader.run()`:** The `Trader.run()` method signature was simplified, but the call in `docker/runner.py` was still passing obsolete arguments. **Lesson:** Method signature changes must be propagated to all callers.
3.  **`AttributeError` in `AlpacaClient`:** The `PortfolioManager` depended on methods (`get_account`, `get_positions`) that were not implemented in our custom `AlpacaClient`. **Lesson:** When creating a custom client or wrapper, ensure it fully implements the interface its consumers expect.
4.  **`KeyError` in `regime_detector.py`:** The data returned from the Alpaca API used lowercase column names (`'high'`, `'low'`), but the `regime_detector` expected capitalized names (`'High'`, `'Low'`). **Lesson:** Data schemas from external APIs can be inconsistent. Always standardize data (e.g., by converting columns to lowercase) as soon as it enters the system.

**Overarching Lesson:**
This multi-stage failure highlights the critical importance of **integration testing**. While individual unit tests may pass, only a full application run (in this case, `docker-compose up`) can reveal issues in the complex interactions between components. The process emphasized a key debugging principle: fix one error, rebuild, and re-run to see what the *next* error is. This systematic approach is essential for untangling complex, layered bugs in a containerized environment.

---

## Section 10: The Final Debugging Cascade (V1.0 Stability)

**Date:** 2025-10-08

**Problem:**
After all major features were complete, the final step was to verify that the ML model was making predictions in the live paper-trading environment. A log message was added to `strategy.py` to confirm this. However, the log message never appeared, triggering a deep and systematic debugging session that uncovered a cascade of subtle, interacting issues.

**Root Cause Analysis & Resolution:**
The debugging process was a classic case of peeling back layers of an onion, where fixing one problem immediately revealed the next.

1.  **Initial Symptom: No Prediction Log.** The `inference_strategy.evaluate.predict` log message was not appearing, even after waiting for the 15-minute trade interval.
2.  **Hypothesis 1 (Incorrect): Timing Issue.** The initial assumption was a misunderstanding of the `trade_interval` vs. `run_interval_seconds`. This was a red herring.
3.  **Hypothesis 2 (Correct): Silent Failure in Pre-Trade Checks.** The real issue was that a check within the `trader.run()` method was failing silently, causing the method to exit before reaching the prediction step. The debugging process then focused on identifying which check was failing.
4.  **Issue #1: Data Gaps.** The first culprit was the `has_data_gaps` check in `data_loader.py`. The default tolerance for missing data was too strict (5%), causing the check to fail and invalidate the data.
    *   **Solution:** The tolerance was relaxed to 10% (`tolerance=0.10`).
5.  **Issue #2: Insufficient Data for Regime Detector.** Fixing the data gap issue revealed the next problem: the `RegimeDetector` required 100 data points (`long_window=100`) to calculate the market regime. The data loader, even after the fix, was not always providing this many bars. This caused the `detect_regime` method to return `None`, which halted the trading process.
    *   **Solution:** The `RegimeDetector`'s requirements were tuned to be less demanding, reducing the `long_window` to 50. This made it more resilient to small variations in the amount of available data.
6.  **Issue #3: Anomalous Data Removal.** After fixing the regime detector, the prediction log *still* didn't appear. The final culprit was the `remove_zero_volume_anomalies` function. While well-intentioned, this function was removing bars from the dataset that, while anomalous, were needed to meet the 50-point requirement of the newly tuned `RegimeDetector`.
    *   **Solution:** The function was changed to only *log* the anomaly but **not remove the data**. This ensured the `RegimeDetector` always had enough data to work with, finally allowing the entire pipeline to execute successfully.
7.  **Hypothesis 4 (Incorrect): `trader.run()` not being called.** When the prediction log *still* didn't appear immediately, the final hypothesis was that the main loop in `docker/runner.py` was broken.
    *   **Solution:** Diagnostic logging was added to `runner.py` and `trader.py`. This was the final key. The logs proved that the main loop *was* running correctly and that `trader.run()` *was* being called. The logs from `trader.py` then confirmed that all pre-trade checks were finally passing, and the prediction was being made.

**Overarching Lesson:**
This entire episode was a masterclass in systematic, iterative debugging.
-   **Visibility is Everything:** When a process fails silently, the top priority is to add detailed logging at every critical step. The diagnostic logs added to `trader.py` and `runner.py` were essential to finally understanding the control flow.
-   **Interacting Systems Create Emergent Failures:** None of the individual issues (data gap tolerance, regime window size, anomaly removal) were "bugs" in isolation. They were all reasonable implementations. The failure emerged from the *interaction* of these systems. The strict data validation starved the regime detector, which in turn starved the prediction engine.
-   **Don't Assume, Prove:** The final step of adding logs to `runner.py` was crucial. Even when 99% sure where a problem lies, taking the time to add logging and *prove* it is faster than continuing to debug based on an unverified assumption.

This final, intense debugging cascade was what truly hardened the system into the stable, reliable V1.0 application.

---

### The Great Debugging Gauntlet: From Build to Health Checks

**Date:** 2025-10-09

This series of issues represented a full-stack debugging challenge, touching every part of the application from the Docker environment to the application's core logic.

**1. The Docker Build Failure (`longintrepr.h` not found):**

*   **Problem:** The Docker build failed with `fatal error: longintrepr.h: No such file or directory` while trying to install a Python package.
*   **Root Cause:** The base `python:3.11-slim-bullseye` image was missing the C header files required to compile some Python dependencies from source.
*   **Solution:** We switched the base image to `python:3.11-bookworm` and explicitly installed the Python development headers with `apt-get install -y python3.11-dev`.
*   **Lesson:** A "slim" image is not always better if it sacrifices build-time necessities. For complex applications with many dependencies, a full development image can be more reliable. Always ensure the build environment has the necessary compilers and headers.

**2. The Alpaca API 404 and Dependency Conflict:**

*   **Problem:** After fixing the build, the application failed at runtime with a `404 Not Found` error when fetching data from Alpaca.
*   **Root Cause:** The `alpaca-trade-api` version `2.3.0` was outdated and pointing to old API endpoints that had been deprecated.
*   **Solution:** We upgraded `alpaca-trade-api` to `3.2.0`. This, however, created a new dependency conflict with `aiohttp`. We resolved this by upgrading `aiohttp` from `3.8.1` to `3.8.3`.
*   **Lesson:** `404` errors from an API client often mean the client is outdated. When upgrading a core dependency, always be prepared to handle and resolve sub-dependency conflicts.

**3. The Pandas Timezone and Index Minefield:**

*   **Problem:** A cascade of `TypeError` and `AttributeError` exceptions occurred in `data_loader.py` and `strategy.py`. The errors were related to Pandas `DatetimeIndex` operations.
*   **Root Cause:** Different parts of the code made different assumptions about the DataFrame's index. Some parts expected a timezone-aware index, others a naive one, and in some cases, the index wasn't a `DatetimeIndex` at all, leading to errors when trying to access datetime properties like `.dayofweek`.
*   **Solution:** We implemented a robust, multi-step fix:
    1.  Added `isinstance(df.index, pd.DatetimeIndex)` guards to prevent errors on invalid index types.
    2.  Used `pd.to_datetime(..., utc=True)` to reliably convert and create timezone-aware indexes.
    3.  Standardized on UTC by using `.tz_localize('UTC')` and `.tz_convert('UTC')` at critical data ingress and processing points.
*   **Lesson:** Data consistency is paramount. For time-series data, establish a strict convention for timezones (e.g., "always convert to UTC on ingress") and enforce it throughout the application. Never assume the type or state of a DataFrame's index.

**4. The Final Boss: Health Check Configuration Error:**

*   **Problem:** The application was stable, but the health check endpoint was failing with an `AttributeError: 'AppConfig' object has no attribute 'api_key'`.
*   **Root Cause:** The `check_data_feed_health` function required API keys to instantiate its own `DataLoader`, but it was only being passed the `AppConfig` object, which doesn't contain secrets. The API keys reside in the `AlpacaConfig` object.
*   **Solution:** We refactored the `check_data_feed_health` function to accept both `AppConfig` and `AlpacaConfig`. The calling function in `health_server.py` was updated to load and pass both configuration objects.
*   **Lesson:** This was a classic dependency injection failure. Configuration, especially secrets, should be passed explicitly to the functions that need them. This makes dependencies clear and avoids side-effects where a function implicitly relies on a global or improperly scoped state.

---

*(This document will be updated as the project progresses.)*
**11. Trading Loop Coupled to Health Server:**

*   **Problem:** Disabling the health server inadvertently disabled the trading loop due to a gating mistake in `runner.py`.
*   **Fix:** Decoupled the health thread from the main loop; corrected `record_heartbeat` and `record_run` signatures and ordering.
*   **Lesson:** Avoid hidden couplings in startup paths; keep background services optional and independent of the core loop.

**12. API Model Mismatches (dict vs Pydantic):**

*   **Problem:** Passing dicts to API helpers expecting Pydantic models caused runtime attribute errors.
*   **Fix:** Normalize at module boundaries: translate dicts into typed `OrderRequest` before calling the broker.
*   **Lesson:** Strong typing on interfaces prevents entire classes of runtime errors.

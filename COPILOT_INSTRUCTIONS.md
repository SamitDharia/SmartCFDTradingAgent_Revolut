# 🧠 COPILOT_INSTRUCTIONS.md  
**Mission:**  
Transform this codebase into a fully autonomous, intelligent trading system — the “AI Trading God.”  
The system must trade automatically, learn continuously, and improve its performance over time.

---

## 🎯 Primary Goals
1. **Full-auto operation** — remove all manual trade execution, Telegram modules, and crypto backfill scripts.  
2. **Use Alpaca API** for execution across:
   - Stocks
   - Crypto
   - Commodities
   - Forex  
   ✅ Add additional tickers for each category to diversify trading.
3. **Machine Learning Core**
   - The system must **learn, update, and optimize** strategies and parameters automatically.
   - Adapt between **conservative** and **aggressive** modes based on performance and risk.
   - Objective: **maximize profit with calculated risk**, no manual intervention.
4. **Continuous Improvement**
   - The AI must evolve and get smarter every run.
   - Apply reinforcement/auto-tuning or similar mechanisms.
   - Learn from historical trades and current performance metrics.

---

## 🧹 Codebase Cleanup
- Remove all Telegram-related scripts, functions, and config references.
- Remove manual-trade and reporting components.
- Remove crypto log backfill code — not required for performance metrics.
- Ensure only **Alpaca** trade logging remains.
- Logging system should track:
  - Trade executions
  - Strategy used
  - Parameters applied
  - Performance summary
- All unused or legacy files must be **deleted** if not referenced anywhere else.
- Verify imports and dependencies after cleanup.

---

## ⚙️ Configuration
- `.env` file must support **switching between paper and live trade keys** easily.
- Add validation to ensure correct keys are loaded depending on mode.

---

## 🧠 Machine Learning & Strategy Engine
- Implement ML models or adaptive logic that:
  - Monitors performance of each strategy.
  - Adjusts indicator parameters automatically (EMA, RSI, MACD, ADX, Bollinger Bands, etc.).
  - Decides when to shift between strategies or risk levels.
- Include modular structure for future expansion (e.g., new indicators or AI strategies).
- Document the logic clearly in the code comments and README.

---

## 📊 Daily Digest
- Generate a **data-rich daily digest** summarizing:
  - Strategies used
  - Performance of each trade
  - Key stats (profit/loss %, drawdown, Sharpe ratio, etc.)
  - Notable trends or insights
  - Recap of the previous day’s performance  
- Keep the tone **global, clear, and engaging** so the digest is understandable by both you and external viewers.
- Format: HTML or Markdown summary file.
- Goal: make it look and feel **premium** — future-ready for monetization.

---

## 💻 Streamlit Dashboard
- Rebuild or refine the Streamlit dashboard with:
  - **Apple-like** clean, modern design (white space, crisp typography).
  - Interactive controls for visualization and simulation.
  - Real-time performance and strategy indicators.
  - A “futuristic” view showing how the trading AI operates.
- The dashboard should **wow** anyone who sees it — sleek, professional, and clear.

---

## 🧩 Architecture & Performance
- Simplify project structure — remove redundant folders and unused modules.
- Verify that dependencies and imports are consistent post-cleanup.
- Ensure modularity for adding ML features later.
- Prioritize efficiency and maintainability.

---

## ✅ Deliverables
1. Clean, functional, and self-contained codebase.
2. Updated README explaining the system, configuration, and usage.
3. Streamlit dashboard redesign.
4. Working daily digest generator.
5. Verified live/paper Alpaca integration.
6. Documented list of deleted/merged files for traceability.

---

## 🤖 Attitude & Mindset
Approach this refactor as if you are creating **the smartest trading AI ever built**.  
Every decision should improve:
- Intelligence  
- Efficiency  
- Sustainability  
- Profitability  

This code should **get smarter every single time it runs**.

---

## ❓If Clarification Is Needed
Before deleting or refactoring a major subsystem, ask:
- “Is this referenced elsewhere?”
- “Does this component serve a purpose in the new architecture?”
- “Is there a simpler or smarter way to achieve the same result?”

If unsure, **comment in the PR** with questions before removal.

---

## 🚀 Final Objective
Create a streamlined, autonomous trading system that:
- Executes trades automatically (via Alpaca).
- Learns and optimizes its own strategy.
- Generates beautiful daily digests.
- Displays an interactive, futuristic dashboard.
- Is maintainable, organized, and ready for future AI expansions.

**If there was an AI Trading God — this would be it.**

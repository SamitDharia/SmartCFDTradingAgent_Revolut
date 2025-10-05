# Cloud-first minimal deploy

This PR adds a Docker image and a simple runner so the agent can run in the cloud even if your laptop is offline. It doesn’t trade yet; it verifies connectivity, stays alive, and is the foundation for the real agent runtime in the next PR.

## One-time setup
1. Copy the template and edit your local secrets (keep ALPACA_ENV=paper):
   cp .env.deploy.example .env
2. Build:
   docker compose build
3. Run:
   docker compose up -d
4. Logs:
   docker compose logs -f app

What you’ll see: periodic connectivity checks to Alpaca, exponential backoff during outages, and a steady heartbeat to prove the container runtime is stable.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates bash && \
    rm -rf /var/lib/apt/lists/*

# Copy the repo and install Python deps (fallback if requirements.txt missing)
COPY . /app

RUN python -m pip install --upgrade pip && \
    if [ -f requirements.txt ]; then \
      pip install -r requirements.txt; \
    else \
      pip install requests pytest; \
    fi

# Entrypoint + healthcheck
RUN chmod +x /app/docker/entrypoint.sh
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python /app/docker/healthcheck.py

CMD ["bash", "/app/docker/entrypoint.sh"]

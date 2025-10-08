# Using a slim Python image for a smaller footprint
FROM python:3.11-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates bash && \
    rm -rf /var/lib/apt/lists/*

# --- Optimized Dependency Installation ---
# Copy only the dependency files to leverage Docker cache
COPY requirements.txt pyproject.toml /app/

# Install Python dependencies
RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt

# --- Application Code ---
# Copy the rest of the application code
COPY . /app

# Make scripts executable
RUN chmod +x /app/docker/entrypoint.sh
RUN chmod +x /app/scripts/send_digest.sh
RUN chmod +x /app/scripts/send_snapshot.sh

# Set the entrypoint for the container
ENTRYPOINT ["/app/docker/entrypoint.sh"]

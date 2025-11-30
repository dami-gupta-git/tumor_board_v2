# Backend Dockerfile for TumorBoard Flask API
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY backend/requirements.txt /app/backend/requirements.txt

# Copy main project requirements and pyproject.toml for package installation
COPY requirements.txt pyproject.toml README.md /app/
COPY src/ /app/src/

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt && \
    pip install -r /app/backend/requirements.txt && \
    pip install -e /app

# Copy backend application code
COPY backend/ /app/backend/

# Create a non-root user
RUN useradd -m -u 1000 tumorboard && \
    chown -R tumorboard:tumorboard /app
USER tumorboard

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/health')"

# Run the application with uvicorn via gunicorn for async support and production stability
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "backend.app:app"]

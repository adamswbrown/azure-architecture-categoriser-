# Azure Architecture Categoriser
# Multi-stage build for smaller image size

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files (README.md required by pyproject.toml)
COPY pyproject.toml README.md ./
COPY src/ src/

# Install the package with all dependencies
RUN pip install --no-cache-dir ".[recommendations-app,gui]"

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (git for catalog updates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source and catalog
COPY src/ src/
COPY docker-entrypoint.sh /app/
COPY architecture-catalog.json /app/

# Set permissions
RUN chmod +x /app/docker-entrypoint.sh \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose Streamlit ports
EXPOSE 8501 8502

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Environment variables for Streamlit
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_CORS=false
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

ENTRYPOINT ["/app/docker-entrypoint.sh"]

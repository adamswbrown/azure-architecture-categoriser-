#!/bin/bash
set -e

# Azure Architecture Categoriser - Container Entrypoint
# Starts the unified multi-page Streamlit application

echo "Starting Azure Architecture Recommender..."
echo "  - Recommendations page (main)"
echo "  - Catalog Stats page"
echo "  - Catalog Builder page"

# Start the unified app (multi-page Streamlit with pages/ directory)
exec streamlit run src/architecture_recommendations_app/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true

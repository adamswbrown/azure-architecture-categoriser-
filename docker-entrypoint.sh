#!/bin/bash
set -e

# Azure Architecture Categoriser - Container Entrypoint
# Starts both Streamlit applications

echo "Starting Azure Architecture Categoriser..."

# Start Catalog Builder GUI in background (port 8502)
streamlit run src/catalog_builder_gui/app.py \
    --server.port 8502 \
    --server.address 0.0.0.0 \
    --server.headless true \
    &

# Start Recommendations App in foreground (port 8501)
exec streamlit run src/architecture_recommendations_app/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true

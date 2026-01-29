#!/bin/bash
# Start the Catalog Builder GUI
# Visual interface for building architecture catalogs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting Catalog Builder GUI..."
echo "Project root: $PROJECT_ROOT"

# Change to project root to ensure correct paths
cd "$PROJECT_ROOT"

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "Error: streamlit is not installed."
    echo "Install with: pip install -e \".[gui]\""
    exit 1
fi

# Start the app on port 8502 (to avoid conflict with recommendations app on 8501)
streamlit run src/catalog_builder_gui/app.py --server.port 8502 "$@"

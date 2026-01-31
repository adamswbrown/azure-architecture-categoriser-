#!/bin/bash
# Start the Azure Architecture Recommendations App
# Customer-facing web application for architecture recommendations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting Azure Architecture Recommendations App..."
echo "Project root: $PROJECT_ROOT"

# Change to project root to ensure correct paths
cd "$PROJECT_ROOT"

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "Error: streamlit is not installed."
    echo "Install with: pip install -e \".[recommendations-app]\""
    exit 1
fi

# Check if catalog exists
if [ ! -f "architecture-catalog.json" ]; then
    echo "Warning: architecture-catalog.json not found in project root."
    echo "The app will look for it in default locations."
fi

# Start the app
streamlit run src/architecture_recommendations_app/Recommendations.py "$@"

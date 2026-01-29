# Start the Azure Architecture Recommendations App
# Customer-facing web application for architecture recommendations

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "Starting Azure Architecture Recommendations App..."
Write-Host "Project root: $ProjectRoot"

# Change to project root to ensure correct paths
Set-Location $ProjectRoot

# Check if streamlit is available
try {
    $null = Get-Command streamlit -ErrorAction Stop
} catch {
    Write-Host "Error: streamlit is not installed." -ForegroundColor Red
    Write-Host 'Install with: pip install -e ".[recommendations-app]"'
    exit 1
}

# Check if catalog exists
if (-not (Test-Path "architecture-catalog.json")) {
    Write-Host "Warning: architecture-catalog.json not found in project root." -ForegroundColor Yellow
    Write-Host "The app will look for it in default locations."
}

# Start the app
streamlit run src/architecture_recommendations_app/app.py $args

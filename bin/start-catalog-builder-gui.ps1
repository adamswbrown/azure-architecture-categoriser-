# Start the Catalog Builder GUI
# Visual interface for building architecture catalogs

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "Starting Catalog Builder GUI..."
Write-Host "Project root: $ProjectRoot"

# Change to project root to ensure correct paths
Set-Location $ProjectRoot

# Check if streamlit is available
try {
    $null = Get-Command streamlit -ErrorAction Stop
} catch {
    Write-Host "Error: streamlit is not installed." -ForegroundColor Red
    Write-Host 'Install with: pip install -e ".[gui]"'
    exit 1
}

# Start the app
streamlit run src/catalog_builder_gui/app.py $args

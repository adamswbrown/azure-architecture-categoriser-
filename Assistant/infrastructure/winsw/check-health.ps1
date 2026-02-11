#Requires -Version 5.1

<#
.SYNOPSIS
    Health check for Dr.Migrate Assistant services

.DESCRIPTION
    This script performs comprehensive health checks on the Agents Server and/or CopilotKit Proxy.
    It verifies:
    - Windows Service status
    - HTTP endpoint availability
    - Response times
    - Port availability
    - Process status

.PARAMETER ServiceName
    Which service(s) to check: 'all', 'agents', or 'copilotkit' (default: all)

.PARAMETER Detailed
    If specified, includes detailed diagnostic information

.PARAMETER Json
    If specified, outputs results in JSON format

.PARAMETER ContinuousMonitor
    If specified, runs health checks in a loop with specified interval

.PARAMETER MonitorInterval
    Interval in seconds for continuous monitoring (default: 60)

.EXAMPLE
    .\check-health.ps1
    Runs basic health check on both services

.EXAMPLE
    .\check-health.ps1 -ServiceName agents
    Checks only Agents Server

.EXAMPLE
    .\check-health.ps1 -Detailed
    Runs detailed health check with diagnostics

.EXAMPLE
    .\check-health.ps1 -Json
    Outputs results in JSON format

.EXAMPLE
    .\check-health.ps1 -ContinuousMonitor -MonitorInterval 30
    Monitors health every 30 seconds

.NOTES
    Author: Dr.Migrate Team
    Exit Codes:
    - 0: All services healthy
    - 1: One or more services unhealthy
    - 2: Critical failure (no services available)
#>

[CmdletBinding()]
param(
    [ValidateSet('all', 'agents', 'copilotkit')]
    [string]$ServiceName = 'all',
    [switch]$Detailed,
    [switch]$Json,
    [switch]$ContinuousMonitor,
    [int]$MonitorInterval = 60
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# Service Definitions
$AllServices = @{
    'agents' = @{
        Name = "DrMigrate-AgentsServer"
        DisplayName = "Agents Server"
        Port = 8002
        HealthEndpoint = "http://localhost:8002/health"
        ProcessName = "uv"
    }
    'copilotkit' = @{
        Name = "DrMigrate-CopilotKitProxy"
        DisplayName = "CopilotKit Proxy"
        Port = 8001
        HealthEndpoint = "http://localhost:8001/health"
        ProcessName = "node"
    }
}

# Determine which services to check
$servicesToCheck = @()
switch ($ServiceName.ToLower()) {
    'all' {
        $servicesToCheck = @('agents', 'copilotkit')
    }
    'agents' {
        $servicesToCheck = @('agents')
    }
    'copilotkit' {
        $servicesToCheck = @('copilotkit')
    }
}

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White",
        [switch]$NoNewline
    )

    if (-not $Json) {
        if ($NoNewline) {
            Write-Host $Message -ForegroundColor $Color -NoNewline
        } else {
            Write-Host $Message -ForegroundColor $Color
        }
    }
}

function Test-ServiceStatus {
    param([string]$ServiceName)

    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue

    if (-not $service) {
        return @{
            Status = "NOT_INSTALLED"
            Healthy = $false
            Details = "Service not found"
        }
    }

    $isHealthy = $service.Status -eq 'Running'

    return @{
        Status = $service.Status.ToString().ToUpper()
        Healthy = $isHealthy
        StartType = $service.StartType.ToString()
        Details = if ($isHealthy) { "Service is running" } else { "Service is $($service.Status)" }
    }
}

function Test-PortListening {
    param([int]$Port)

    try {
        $tcpConnections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return @{
            Listening = $tcpConnections.Count -gt 0
            ProcessId = if ($tcpConnections) { $tcpConnections[0].OwningProcess } else { $null }
        }
    } catch {
        return @{
            Listening = $false
            ProcessId = $null
        }
    }
}

function Test-HttpEndpoint {
    param([string]$Url, [int]$TimeoutSec = 5)

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
        $stopwatch.Stop()

        return @{
            Available = $true
            StatusCode = $response.StatusCode
            ResponseTime = $stopwatch.ElapsedMilliseconds
            Details = "HTTP $($response.StatusCode) in $($stopwatch.ElapsedMilliseconds)ms"
        }
    } catch {
        $stopwatch.Stop()

        return @{
            Available = $false
            StatusCode = $null
            ResponseTime = $stopwatch.ElapsedMilliseconds
            Details = $_.Exception.Message
        }
    }
}

function Get-ProcessInfo {
    param([int]$ProcessId)

    if (-not $ProcessId) {
        return $null
    }

    try {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        return @{
            Name = $process.ProcessName
            Id = $process.Id
            CPU = [math]::Round($process.CPU, 2)
            Memory = [math]::Round($process.WorkingSet64 / 1MB, 2)
            StartTime = $process.StartTime
            Uptime = (Get-Date) - $process.StartTime
        }
    } catch {
        return $null
    }
}

function Get-ServiceHealth {
    param([hashtable]$ServiceConfig)

    $health = @{
        Name = $ServiceConfig.DisplayName
        ServiceName = $ServiceConfig.Name
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }

    # Check Windows Service
    $serviceStatus = Test-ServiceStatus -ServiceName $ServiceConfig.Name
    $health.Service = $serviceStatus

    # Check Port
    $portStatus = Test-PortListening -Port $ServiceConfig.Port
    $health.Port = @{
        Number = $ServiceConfig.Port
        Listening = $portStatus.Listening
    }

    # Check HTTP Endpoint
    $httpStatus = Test-HttpEndpoint -Url $ServiceConfig.HealthEndpoint
    $health.Http = $httpStatus

    # Get Process Info (if port is listening)
    if ($portStatus.ProcessId) {
        $processInfo = Get-ProcessInfo -ProcessId $portStatus.ProcessId
        $health.Process = $processInfo
    }

    # Overall health determination
    $health.Healthy = $serviceStatus.Healthy -and $httpStatus.Available
    $health.Status = if ($health.Healthy) { "HEALTHY" } else { "UNHEALTHY" }

    return $health
}

function Show-HealthReport {
    param([array]$HealthData)

    Write-ColorOutput "`n=== Dr.Migrate Assistant Health Report ===" "Cyan"
    Write-ColorOutput "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" "Gray"
    Write-ColorOutput ""

    $allHealthy = $true

    foreach ($health in $HealthData) {
        $statusColor = if ($health.Healthy) { "Green" } else { "Red" }
        $statusIcon = if ($health.Healthy) { "[OK]" } else { "[FAIL]" }

        Write-ColorOutput "$statusIcon $($health.Name)" $statusColor
        Write-ColorOutput "  Service: $($health.Service.Status)" $(if ($health.Service.Healthy) { "Green" } else { "Yellow" })
        Write-ColorOutput "  HTTP: " "Gray" -NoNewline
        Write-ColorOutput $health.Http.Details $(if ($health.Http.Available) { "Green" } else { "Red" })

        if ($Detailed) {
            Write-ColorOutput "  Port $($health.Port.Number): $(if ($health.Port.Listening) { 'Listening' } else { 'Not Listening' })" "Gray"

            if ($health.Process) {
                $uptime = "{0:hh\:mm\:ss}" -f $health.Process.Uptime
                Write-ColorOutput "  Process: $($health.Process.Name) (PID: $($health.Process.Id))" "Gray"
                Write-ColorOutput "    CPU: $($health.Process.CPU)s | Memory: $($health.Process.Memory) MB | Uptime: $uptime" "Gray"
            }
        }

        Write-ColorOutput ""

        if (-not $health.Healthy) {
            $allHealthy = $false
        }
    }

    # Summary
    $healthyCount = ($HealthData | Where-Object { $_.Healthy }).Count
    $totalCount = $HealthData.Count

    Write-ColorOutput "=== Summary ===" "Cyan"
    Write-ColorOutput "Services: $healthyCount/$totalCount healthy" $(if ($allHealthy) { "Green" } else { "Yellow" })

    if (-not $allHealthy) {
        Write-ColorOutput "`nRecommendations:" "Yellow"
        foreach ($health in $HealthData | Where-Object { -not $_.Healthy }) {
            if ($health.Service.Status -ne "RUNNING") {
                Write-ColorOutput "  - Restart $($health.Name): .\restart-services.ps1" "Yellow"
            } elseif (-not $health.Http.Available) {
                Write-ColorOutput "  - Check $($health.Name) logs for errors" "Yellow"
            }
        }
    }

    Write-ColorOutput ""

    return $allHealthy
}

function Show-JsonReport {
    param([array]$HealthData)

    $report = @{
        Timestamp = Get-Date -Format "o"
        Services = $HealthData
        Summary = @{
            Total = $HealthData.Count
            Healthy = ($HealthData | Where-Object { $_.Healthy }).Count
            Unhealthy = ($HealthData | Where-Object { -not $_.Healthy }).Count
            OverallStatus = if (($HealthData | Where-Object { -not $_.Healthy }).Count -eq 0) { "HEALTHY" } else { "UNHEALTHY" }
        }
    }

    return $report | ConvertTo-Json -Depth 10
}

# Main execution
function Invoke-HealthCheck {
    # Collect health data (only for selected services)
    $healthData = @()
    foreach ($svcKey in $servicesToCheck) {
        $healthData += Get-ServiceHealth -ServiceConfig $AllServices[$svcKey]
    }

    # Display results
    if ($Json) {
        $jsonOutput = Show-JsonReport -HealthData $healthData
        Write-Output $jsonOutput
    } else {
        $allHealthy = Show-HealthReport -HealthData $healthData
    }

    # Determine exit code
    $unhealthyCount = ($healthData | Where-Object { -not $_.Healthy }).Count

    if ($unhealthyCount -eq 0) {
        return 0  # All healthy
    } elseif ($unhealthyCount -eq $healthData.Count) {
        return 2  # All unhealthy (critical)
    } else {
        return 1  # Some unhealthy
    }
}

# Run health check
if ($ContinuousMonitor) {
    Write-ColorOutput "Starting continuous health monitoring (Ctrl+C to stop)..." "Cyan"
    Write-ColorOutput "Check interval: $MonitorInterval seconds" "Gray"
    Write-ColorOutput ""

    while ($true) {
        $exitCode = Invoke-HealthCheck

        if (-not $Json) {
            Write-ColorOutput "Next check in $MonitorInterval seconds..." "Gray"
            Write-ColorOutput ("=" * 80) "DarkGray"
        }

        Start-Sleep -Seconds $MonitorInterval
    }
} else {
    $exitCode = Invoke-HealthCheck
    exit $exitCode
}

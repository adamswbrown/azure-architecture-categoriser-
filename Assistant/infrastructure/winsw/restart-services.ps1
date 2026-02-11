#Requires -Version 5.1
#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Restarts Dr.Migrate Assistant services

.DESCRIPTION
    This script safely restarts both the Agents Server and CopilotKit Proxy Windows Services.
    It handles:
    - Graceful service stop
    - Service restart
    - Health verification
    - Status reporting

.PARAMETER ServiceName
    Optional. Restart only a specific service. Valid values: 'agents', 'copilotkit', 'all'
    Default: 'all'

.PARAMETER NoHealthCheck
    If specified, skips health endpoint verification after restart

.EXAMPLE
    .\restart-services.ps1
    Restarts both services with health checks

.EXAMPLE
    .\restart-services.ps1 -ServiceName agents
    Restarts only the agents server

.EXAMPLE
    .\restart-services.ps1 -NoHealthCheck
    Restarts services without health verification

.NOTES
    Author: Dr.Migrate Team
    Requires: Administrator privileges
#>

[CmdletBinding()]
param(
    [ValidateSet('all', 'agents', 'copilotkit')]
    [string]$ServiceName = 'all',
[switch]$NoHealthCheck
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$ScriptRoot = $PSScriptRoot

# Service Definitions
$AllServices = @{
    'agents' = @{
        Name = "DrMigrate-AgentsServer"
        DisplayName = "Dr.Migrate Agents Server"
        Port = 8002
        HealthEndpoint = "http://localhost:8002/health"
        StopTimeout = 30
    }
    'copilotkit' = @{
        Name = "DrMigrate-CopilotKitProxy"
        DisplayName = "Dr.Migrate CopilotKit Proxy"
        Port = 8001
        HealthEndpoint = "http://localhost:8001/health"
        StopTimeout = 15
    }
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz"
    $scriptName = if ($PSCommandPath) { Split-Path -Leaf $PSCommandPath } else { "Interactive" }
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN" { "Yellow" }
        "SUCCESS" { "Green" }
        default { "White" }
    }
    Write-Host "$timestamp`t$Level`t[$scriptName] $Message" -ForegroundColor $color
}

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-ServiceCommand {
    param(
        [string]$ServiceName,
        [ValidateSet('start', 'stop')]
        [string]$Action
    )

    $serviceExe = Join-Path $ScriptRoot "$ServiceName.exe"
    if (Test-Path $serviceExe) {
        Write-Log "Using WinSW executable for '$Action': $serviceExe" "INFO"
        & $serviceExe $Action
    }
    else {
        Write-Log "WinSW executable not found at $serviceExe, falling back to Service Control Manager" "WARN"
        if ($Action -eq 'start') {
            Start-Service -Name $ServiceName -ErrorAction Stop
        }
        else {
            Stop-Service -Name $ServiceName -Force -ErrorAction Stop
        }
    }
}

function Stop-ServiceProcessTree {
    <#
    .SYNOPSIS
        Forcefully terminates any orphaned processes for a service.

    .DESCRIPTION
        Cleans up process tree for services that may leave orphaned processes,
        particularly when using process wrappers like UV that spawn child processes.

        Uses two methods:
        1. Find by port binding (primary)
        2. Find UV processes by name (backup)

    .PARAMETER ServiceName
        Name of the Windows service

    .PARAMETER Port
        Port number the service listens on
    #>
    param(
        [string]$ServiceName,
        [int]$Port
    )

    Write-Log "Cleaning up process tree for $ServiceName..." "INFO"

    # Method 1: Find by port binding
    try {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            $pid = $listener.OwningProcess
            Write-Log "Found process on port ${Port}: PID $pid" "INFO"

            # Kill process tree using taskkill /T (kills parent and all children)
            $result = taskkill /F /T /PID $pid 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Log "Process tree terminated successfully" "SUCCESS"
            }
            else {
                Write-Log "taskkill returned exit code $LASTEXITCODE" "WARN"
            }
        }
        else {
            Write-Log "No process found listening on port $Port" "INFO"
        }
    }
    catch {
        Write-Log "Port check failed: $_" "WARN"
    }

    # Method 2: Find UV processes as backup (in case port isn't bound yet or already released)
    try {
        $uvProcesses = Get-Process -Name "uv" -ErrorAction SilentlyContinue
        if ($uvProcesses) {
            foreach ($proc in $uvProcesses) {
                Write-Log "Found orphaned UV process: PID $($proc.Id)" "WARN"
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
    catch {
        Write-Log "UV process check failed: $_" "WARN"
    }

    # Brief wait for cleanup
    Start-Sleep -Milliseconds 500
}

function Restart-AssistantService {
    param(
        [hashtable]$ServiceConfig,
        [switch]$SkipHealthCheck
    )

    $svcName = $ServiceConfig.Name
    $displayName = $ServiceConfig.DisplayName

    Write-Log "Restarting $displayName..." "INFO"

    # Check if service exists
    $service = Get-Service -Name $svcName -ErrorAction SilentlyContinue
    if (-not $service) {
        Write-Log "Service $svcName not found. Please install services first." "ERROR"
        return $false
    }

    # Stop service
    if ($service.Status -eq 'Running') {
        Write-Log "Stopping $displayName..." "INFO"
        try {
            # First: Standard service stop via WinSW executable (preferred) or SCM fallback
            Invoke-ServiceCommand -ServiceName $svcName -Action stop

            # Wait for service to stop (with timeout)
            $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
            $timeout = $ServiceConfig.StopTimeout

            while ($service.Status -ne 'Stopped' -and $stopwatch.Elapsed.TotalSeconds -lt $timeout) {
                Start-Sleep -Milliseconds 500
                $service.Refresh()
            }

            # Second: Process tree cleanup as safety net (if service stopped but processes remain)
            Stop-ServiceProcessTree -ServiceName $svcName -Port $ServiceConfig.Port

            if ($service.Status -ne 'Stopped') {
                Write-Log "Service did not stop within $timeout seconds" "WARN"
            } else {
                Write-Log "Service stopped successfully" "SUCCESS"
            }
        } catch {
            Write-Log "Failed to stop service: $_" "ERROR"

            # Emergency cleanup
            Stop-ServiceProcessTree -ServiceName $svcName -Port $ServiceConfig.Port
            return $false
        }
    } else {
        Write-Log "Service is already stopped (status: $($service.Status))" "INFO"
    }

    # Start service
    Write-Log "Starting $displayName..." "INFO"
    try {
        Invoke-ServiceCommand -ServiceName $svcName -Action start
        Start-Sleep -Seconds 2

        # Verify service is running
        $service.Refresh()
        if ($service.Status -ne 'Running') {
            Write-Log "Service status is $($service.Status) (expected Running)" "WARN"
            return $false
        }

        Write-Log "Service started successfully" "SUCCESS"

        # Health check
        if (-not $SkipHealthCheck) {
            Write-Log "Performing health check..." "INFO"
            Start-Sleep -Seconds 5  # Give service time to initialize

            try {
                $response = Invoke-WebRequest -Uri $ServiceConfig.HealthEndpoint -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    Write-Log "Health check passed" "SUCCESS"
                    return $true
                } else {
                    Write-Log "Health check returned status $($response.StatusCode)" "WARN"
                    return $false
                }
            } catch {
                Write-Log "Health check failed: $_" "WARN"
                Write-Log "Service may still be initializing..." "INFO"
                return $false
            }
        }

        return $true
    } catch {
        Write-Log "Failed to start service: $_" "ERROR"
        return $false
    }
}

function Get-ServiceStatus {
    param([string]$ServiceName)

    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $service) {
        return "NOT INSTALLED"
    }
    return $service.Status
}

# Main execution
try {
    Write-Log "=== Dr.Migrate Assistant Services Restart ===" "INFO"

    # Verify administrator privileges
    if (-not (Test-Administrator)) {
        Write-Log "This script must be run as Administrator" "ERROR"
        exit 1
    }

    # Determine which services to restart
    $servicesToRestart = @()

    switch ($ServiceName.ToLower()) {
        'all' {
            $servicesToRestart = @('agents', 'copilotkit')
        }
        'agents' {
            $servicesToRestart = @('agents')
        }
        'copilotkit' {
            $servicesToRestart = @('copilotkit')
        }
    }

    Write-Log "Services to restart: $($servicesToRestart -join ', ')" "INFO"
    Write-Log "" "INFO"

    # Restart services (CopilotKit first to avoid connection errors)
    $results = @{}

    if ($servicesToRestart -contains 'copilotkit') {
        $results['copilotkit'] = Restart-AssistantService -ServiceConfig $AllServices['copilotkit'] -SkipHealthCheck:$NoHealthCheck
        Write-Log "" "INFO"
    }

    if ($servicesToRestart -contains 'agents') {
        $results['agents'] = Restart-AssistantService -ServiceConfig $AllServices['agents'] -SkipHealthCheck:$NoHealthCheck
        Write-Log "" "INFO"
    }

    # Display final status
    Write-Log "=== Final Service Status ===" "INFO"
    foreach ($svcKey in $AllServices.Keys) {
        $svc = $AllServices[$svcKey]
        $status = Get-ServiceStatus -ServiceName $svc.Name
        $statusColor = switch ($status) {
            "Running" { "Green" }
            "Stopped" { "Red" }
            "NOT INSTALLED" { "Yellow" }
            default { "Yellow" }
        }

        Write-Host "  $($svc.DisplayName): " -NoNewline
        Write-Host $status -ForegroundColor $statusColor

        if ($results.ContainsKey($svcKey)) {
            $healthStatus = if ($results[$svcKey]) { "[OK] HEALTHY" } else { "[WARN] NEEDS ATTENTION" }
            $healthColor = if ($results[$svcKey]) { "Green" } else { "Yellow" }
            Write-Host "    Health: " -NoNewline
            Write-Host $healthStatus -ForegroundColor $healthColor
        }
    }

    Write-Log "" "INFO"

    # Exit code based on results
    $allHealthy = $results.Values | Where-Object { $_ -eq $false }
    if ($allHealthy.Count -gt 0) {
        Write-Log "Some services may need attention. Check logs at %ProgramData%\Dr.Migrate\llm for details." "WARN"
        exit 1
    } else {
        Write-Log "All services restarted successfully!" "SUCCESS"
        exit 0
    }

} catch {
    Write-Log "Restart failed: $_" "ERROR"
    exit 1
}

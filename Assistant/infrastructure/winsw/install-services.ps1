#Requires -Version 5.1
#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Installs Dr.Migrate Assistant services using WinSW

.DESCRIPTION
    This script installs the Agents Server and/or CopilotKit Proxy as Windows Services
    using WinSW.NET461.exe. It handles:
    - WinSW binary download and installation
    - Service registration
    - Log directory creation
    - Service startup and verification
    - Dependency validation

.PARAMETER ServiceName
    Which service(s) to install: 'all', 'agents', or 'copilotkit' (default: all)
    Note: CopilotKit depends on AgentsServer

.PARAMETER WinSWVersion
    Version of WinSW to download (default: 2.12.0)

.PARAMETER SkipStart
    If specified, services will be installed but not started

.EXAMPLE
    .\install-services.ps1
    Installs and starts both services

.EXAMPLE
    .\install-services.ps1 -ServiceName agents
    Installs only the Agents Server

.EXAMPLE
    .\install-services.ps1 -ServiceName copilotkit
    Installs only CopilotKit (warns if AgentsServer not installed)

.EXAMPLE
    .\install-services.ps1 -SkipStart
    Installs services without starting them

.NOTES
    Author: Dr.Migrate Team
    Requires: Administrator privileges
    Services Available:
    - DrMigrate-AgentsServer (port 8002)
    - DrMigrate-CopilotKitProxy (port 8001) [depends on AgentsServer]
#>

[CmdletBinding()]
param(
    [ValidateSet('all', 'agents', 'copilotkit')]
    [string]$ServiceName = 'all',
    [string]$WinSWVersion = "2.12.0",
    [switch]$SkipStart
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Configuration
$ScriptRoot = $PSScriptRoot
$AssistantRoot = Split-Path $ScriptRoot -Parent
$WinSWUrl = "https://github.com/winsw/winsw/releases/download/v$WinSWVersion/WinSW-x64.exe"
$WinSWPath = Join-Path $ScriptRoot "WinSW.NET461.exe"

# Service Definitions
$AllServices = @{
    'agents' = @{
        Name = "DrMigrate-AgentsServer"
        DisplayName = "Dr.Migrate Agents Server"
        ConfigFile = "DrMigrate-AgentsServer.xml"
        WorkingDir = $AssistantRoot
        Port = 8002
        HealthEndpoint = "http://localhost:8002/health"
    }
    'copilotkit' = @{
        Name = "DrMigrate-CopilotKitProxy"
        DisplayName = "Dr.Migrate CopilotKit Proxy"
        ConfigFile = "DrMigrate-CopilotKitProxy.xml"
        WorkingDir = Join-Path $AssistantRoot "services\copilotkit-proxy"
        Port = 8001
        HealthEndpoint = "http://localhost:8001/health"
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

function Get-WinSW {
    if (Test-Path $WinSWPath) {
        Write-Log "WinSW already exists at $WinSWPath" "INFO"
        return $WinSWPath
    }

    Write-Log "Downloading WinSW v$WinSWVersion..." "INFO"
    try {
        Invoke-WebRequest -Uri $WinSWUrl -OutFile $WinSWPath -UseBasicParsing
        Write-Log "WinSW downloaded successfully" "SUCCESS"
    } catch {
        Write-Log "Failed to download WinSW: $_" "ERROR"
        throw
    }

    return $WinSWPath
}

function Test-SQLServerDependency {
    <#
    .SYNOPSIS
    Validates that SQL Server Express is available before starting AgentsServer

    .DESCRIPTION
    Checks if MSSQL$SQLEXPRESS service exists and is running.
    If stopped, attempts to start it with timeout.
    Prevents hanging on service startup due to missing dependencies.

    .RETURNS
    $true if SQL Server is available, $false otherwise
    #>

    $sqlServiceName = "MSSQL`$SQLEXPRESS"

    Write-Log "Checking SQL Server dependency ($sqlServiceName)..." "INFO"

    # Check if service exists
    $sqlService = Get-Service -Name $sqlServiceName -ErrorAction SilentlyContinue
    if (-not $sqlService) {
        Write-Log "SQL Server Express service not found" "ERROR"
        Write-Log "AgentsServer requires SQL Server Express to be installed" "ERROR"
        Write-Log "Install SQL Server Express before installing AgentsServer" "ERROR"
        return $false
    }

    # Check if service is running
    if ($sqlService.Status -eq 'Running') {
        Write-Log "SQL Server is running" "SUCCESS"
        return $true
    }

    # Service exists but not running - try to start it
    Write-Log "SQL Server is stopped. Attempting to start..." "WARN"

    try {
        # Start SQL Server with timeout using job
        $startJob = Start-Job -ScriptBlock {
            param($ServiceName)
            Start-Service -Name $ServiceName -ErrorAction Stop
        } -ArgumentList $sqlServiceName

        # Wait up to 60 seconds for SQL Server to start
        $completed = Wait-Job -Job $startJob -Timeout 60

        if ($completed) {
            $result = Receive-Job -Job $startJob -ErrorAction SilentlyContinue
            Remove-Job -Job $startJob -Force

            # Verify it's actually running
            $sqlService = Get-Service -Name $sqlServiceName
            if ($sqlService.Status -eq 'Running') {
                Write-Log "SQL Server started successfully" "SUCCESS"
                return $true
            } else {
                Write-Log "SQL Server failed to start (status: $($sqlService.Status))" "ERROR"
                return $false
            }
        } else {
            # Timeout occurred
            Stop-Job -Job $startJob -ErrorAction SilentlyContinue
            Remove-Job -Job $startJob -Force
            Write-Log "SQL Server start timed out after 60 seconds" "ERROR"
            return $false
        }
    } catch {
        Write-Log "Failed to start SQL Server: $_" "ERROR"
        return $false
    }
}

function Install-Service {
    param(
        [hashtable]$ServiceConfig,
        [string]$WinSWExe
    )

    $serviceName = $ServiceConfig.Name
    $configFile = Join-Path $ScriptRoot $ServiceConfig.ConfigFile
    $serviceExe = Join-Path $ScriptRoot "$serviceName.exe"

    Write-Log "Installing service: $serviceName" "INFO"

    # Verify config file exists
    if (-not (Test-Path $configFile)) {
        Write-Log "Configuration file not found: $configFile" "ERROR"
        throw "Missing configuration file"
    }

    # Check if service already exists
    $existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Log "Service $serviceName already exists. Stopping and removing..." "WARN"
        if ($existingService.Status -eq 'Running') {
            Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }

        # Remove existing service
        # Check if service-specific executable exists (from previous install)
        if (Test-Path $serviceExe) {
            Write-Log "Uninstalling existing service using service-specific WinSW executable..." "INFO"
            & $serviceExe uninstall
        } else {
            Write-Log "Service-specific executable not found, using sc.exe to remove service..." "INFO"
            & sc.exe delete $serviceName | Out-Null
        }

        # Wait for service to be fully removed (handles "marked for deletion" state)
        $maxWaitSeconds = 10
        $waitCount = 0
        while ((Get-Service -Name $serviceName -ErrorAction SilentlyContinue) -and ($waitCount -lt $maxWaitSeconds)) {
            Start-Sleep -Seconds 1
            $waitCount++
        }

        if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
            Write-Log "Service still exists after $maxWaitSeconds seconds. Close Service Manager and retry." "ERROR"
            throw "Service removal timed out - service may be marked for deletion"
        }
    }

    # Copy WinSW.exe to service-specific name
    if (Test-Path $serviceExe) {
        Remove-Item $serviceExe -Force
    }
    Copy-Item $WinSWExe $serviceExe -Force

    # Create centralized log directory (once for all services)
    # No ACL configuration needed - services run as LocalSystem by default which has full access
    $logDir = "$env:ProgramData\Dr.Migrate\llm"
    if (-not (Test-Path $logDir)) {
        Write-Log "Creating centralized log directory: $logDir" "INFO"
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }

    Write-Log "Centralized log directory ready: $logDir" "SUCCESS"

    # Install service
    try {
        & $serviceExe install
        Write-Log "Service $serviceName installed successfully" "SUCCESS"
    } catch {
        Write-Log "Failed to install service $serviceName : $_" "ERROR"
        throw
    }
}

function Start-ServiceWithRetry {
    param(
        [string]$ServiceName,
        [string]$HealthEndpoint,
        [int]$MaxRetries = 3,
        [int]$RetryDelaySeconds = 5
    )
    $serviceExe = Join-Path $ScriptRoot "$ServiceName.exe"

    # Check if service is already running
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service -and $service.Status -eq 'Running') {
        Write-Log "Service $ServiceName is already running" "INFO"

        # Verify health endpoint to ensure it's functioning properly
        Write-Log "Checking health endpoint: $HealthEndpoint" "INFO"
        try {
            $response = Invoke-WebRequest -Uri $HealthEndpoint -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Log "Health check passed for $ServiceName" "SUCCESS"
                return $true
            } else {
                Write-Log "Service running but health check returned status $($response.StatusCode) - will restart" "WARN"
            }
        } catch {
            Write-Log "Service running but health check failed: $_ - will restart" "WARN"
        }

        # Health check failed, restart the service
        Write-Log "Restarting service due to failed health check..." "INFO"
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
    }

    Write-Log "Starting service: $ServiceName" "INFO"

    for ($i = 1; $i -le $MaxRetries; $i++) {
        try {
            # Start service with timeout to prevent indefinite hangs on dependency resolution
            Write-Log "Attempt $i of $MaxRetries - Starting service..." "INFO"

            $startJob = Start-Job -ScriptBlock {
                param($SvcName, $SvcExe)
                if (Test-Path $SvcExe) {
                    & $SvcExe start
                } else {
                    Start-Service -Name $SvcName -ErrorAction Stop
                }
            } -ArgumentList $ServiceName, $serviceExe

            # Wait up to 30 seconds for service start (includes dependency resolution time)
            $completed = Wait-Job -Job $startJob -Timeout 30

            if (-not $completed) {
                # Timeout occurred - likely dependency issue
                Stop-Job -Job $startJob -ErrorAction SilentlyContinue
                Remove-Job -Job $startJob -Force
                throw "Service start timed out after 30 seconds (check service dependencies)"
            }

            # Check if job completed successfully
            $jobError = Receive-Job -Job $startJob -ErrorAction SilentlyContinue 2>&1
            Remove-Job -Job $startJob -Force

            if ($jobError -and $jobError -match "error") {
                throw "Service start failed: $jobError"
            }

            Start-Sleep -Seconds 3

            # Check service status
            $service = Get-Service -Name $ServiceName
            if ($service.Status -ne 'Running') {
                throw "Service status is $($service.Status)"
            }

            Write-Log "Service $ServiceName started successfully" "SUCCESS"

            # Verify health endpoint (with timeout)
            Write-Log "Checking health endpoint: $HealthEndpoint" "INFO"
            Start-Sleep -Seconds 5  # Give service time to initialize

            try {
                $response = Invoke-WebRequest -Uri $HealthEndpoint -TimeoutSec 10 -UseBasicParsing -ErrorAction SilentlyContinue
                if ($response.StatusCode -eq 200) {
                    Write-Log "Health check passed for $ServiceName" "SUCCESS"
                } else {
                    Write-Log "Health check returned status $($response.StatusCode)" "WARN"
                }
            } catch {
                Write-Log "Health check failed (service may still be initializing): $_" "WARN"
            }

            return $true
        } catch {
            Write-Log "Attempt $i/$MaxRetries failed: $_" "WARN"
            if ($i -lt $MaxRetries) {
                Write-Log "Retrying in $RetryDelaySeconds seconds..." "INFO"
                Start-Sleep -Seconds $RetryDelaySeconds
            }
        }
    }

    Write-Log "Failed to start service $ServiceName after $MaxRetries attempts" "ERROR"
    return $false
}

# Main execution
try {
    Write-Log "=== Dr.Migrate Assistant Services Installation ===" "INFO"

    # Verify administrator privileges
    if (-not (Test-Administrator)) {
        Write-Log "This script must be run as Administrator" "ERROR"
        exit 1
    }

    # Determine which services to install
    $servicesToInstall = @()
    switch ($ServiceName.ToLower()) {
        'all' {
            # Install in dependency order: agents first
            $servicesToInstall = @('agents', 'copilotkit')
        }
        'agents' {
            $servicesToInstall = @('agents')
        }
        'copilotkit' {
            $servicesToInstall = @('copilotkit')
        }
    }

    Write-Log "Services to install: $($servicesToInstall -join ', ')" "INFO"
    Write-Log "" "INFO"

    # Download/verify WinSW
    $winswExe = Get-WinSW

    # Install services
    foreach ($svcKey in $servicesToInstall) {
        Install-Service -ServiceConfig $AllServices[$svcKey] -WinSWExe $winswExe
    }

    # Start services (unless -SkipStart specified)
    if (-not $SkipStart) {
        Write-Log "" "INFO"
        Write-Log "Starting services..." "INFO"

        foreach ($svcKey in $servicesToInstall) {
            $service = $AllServices[$svcKey]

            # Validate SQL Server dependency for AgentsServer before attempting to start
            if ($svcKey -eq 'agents') {
                $sqlAvailable = Test-SQLServerDependency
                if (-not $sqlAvailable) {
                    Write-Log "Skipping AgentsServer startup - SQL Server dependency not available" "ERROR"
                    Write-Log "AgentsServer service is installed but not started" "WARN"
                    continue
                }
            }

            $started = Start-ServiceWithRetry -ServiceName $service.Name -HealthEndpoint $service.HealthEndpoint
            if (-not $started) {
                Write-Log "Service $($service.Name) failed to start properly" "WARN"
            }
        }
    } else {
        Write-Log "Skipping service startup (-SkipStart specified)" "INFO"
    }

    # Display service status (show all services, not just installed ones)
    Write-Log "" "INFO"
    Write-Log "=== Service Status ===" "INFO"
    foreach ($svcKey in @('agents', 'copilotkit')) {
        $service = $AllServices[$svcKey]
        $svc = Get-Service -Name $service.Name -ErrorAction SilentlyContinue
        if ($svc) {
            $status = $svc.Status
            $statusColor = if ($status -eq 'Running') { "Green" } else { "Yellow" }
            Write-Host "  $($service.DisplayName): " -NoNewline
            Write-Host $status -ForegroundColor $statusColor
        } else {
            Write-Host "  $($service.DisplayName): " -NoNewline
            Write-Host "NOT INSTALLED" -ForegroundColor Gray
        }
    }

    Write-Log "" "INFO"
    Write-Log "Installation completed successfully!" "SUCCESS"
    Write-Log "" "INFO"
    Write-Log "Service Management Commands:" "INFO"
    Write-Log "  View logs: %ProgramData%\Dr.Migrate\llm\DrMigrate-*.log" "INFO"
    Write-Log "  Log location: C:\ProgramData\Dr.Migrate\llm" "INFO"
    Write-Log "  Restart: .\restart-services.ps1" "INFO"
    Write-Log "  Uninstall: .\uninstall-services.ps1" "INFO"
    Write-Log "  Check health: .\check-health.ps1" "INFO"

} catch {
    Write-Log "Installation failed: $_" "ERROR"
    exit 1
}

#Requires -Version 5.1
#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Uninstalls Dr.Migrate Assistant services

.DESCRIPTION
    This script safely uninstalls the Agents Server and/or CopilotKit Proxy Windows Services.
    It handles:
    - Service stopping
    - Service unregistration
    - Optional cleanup of log files
    - Dependency validation

.PARAMETER ServiceName
    Which service(s) to uninstall: 'all', 'agents', or 'copilotkit' (default: all)
    Note: CopilotKit depends on AgentsServer

.PARAMETER KeepLogs
    If specified, log files will be preserved

.PARAMETER Force
    If specified, skips confirmation prompts and dependency warnings

.EXAMPLE
    .\uninstall-services.ps1
    Uninstalls both services with confirmation prompts

.EXAMPLE
    .\uninstall-services.ps1 -ServiceName copilotkit
    Uninstalls only CopilotKit

.EXAMPLE
    .\uninstall-services.ps1 -ServiceName agents
    Uninstalls only AgentsServer (warns if CopilotKit still installed)

.EXAMPLE
    .\uninstall-services.ps1 -Force -KeepLogs
    Uninstalls services without prompts, preserves logs

.NOTES
    Author: Dr.Migrate Team
    Requires: Administrator privileges
#>

[CmdletBinding()]
param(
    [ValidateSet('all', 'agents', 'copilotkit')]
    [string]$ServiceName = 'all',
    [switch]$KeepLogs,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptRoot = $PSScriptRoot
$AssistantRoot = Split-Path $ScriptRoot -Parent

# Service Definitions
$AllServices = @{
    'agents' = @{
        Name = "DrMigrate-AgentsServer"
        DisplayName = "Dr.Migrate Agents Server"
        WorkingDir = $AssistantRoot
    }
    'copilotkit' = @{
        Name = "DrMigrate-CopilotKitProxy"
        DisplayName = "Dr.Migrate CopilotKit Proxy"
        WorkingDir = Join-Path $AssistantRoot "services\copilotkit-proxy"
    }
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN" { "Yellow" }
        "SUCCESS" { "Green" }
        default { "White" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Uninstall-Service {
    param(
        [hashtable]$ServiceConfig
    )

    $serviceName = $ServiceConfig.Name

    # Check for service executable (infrastructure\winsw\)
    $serviceExe = Join-Path $ScriptRoot "$serviceName.exe"

    Write-Log "Uninstalling service: $serviceName" "INFO"

    # Check if service exists
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if (-not $service) {
        Write-Log "Service $serviceName not found (may already be uninstalled)" "WARN"

        # Clean up executable if it exists
        if (Test-Path $serviceExe) {
            Remove-Item $serviceExe -Force
            Write-Log "Removed service executable: $serviceExe" "INFO"
        }

        return
    }

    # Stop service if running
    if ($service.Status -eq 'Running') {
        Write-Log "Stopping service $serviceName..." "INFO"
        try {
            Stop-Service -Name $serviceName -Force -ErrorAction Stop
            Start-Sleep -Seconds 3
            Write-Log "Service stopped successfully" "SUCCESS"
        } catch {
            Write-Log "Failed to stop service: $_" "WARN"
            Write-Log "Attempting to continue with uninstallation..." "INFO"
        }
    }

    # Uninstall service
    if (Test-Path $serviceExe) {
        try {
            & $serviceExe uninstall
            Start-Sleep -Seconds 2

            # Wait for service to be fully removed (handles "marked for deletion" state)
            $maxWaitSeconds = 10
            $waitCount = 0
            while ((Get-Service -Name $serviceName -ErrorAction SilentlyContinue) -and ($waitCount -lt $maxWaitSeconds)) {
                Start-Sleep -Seconds 1
                $waitCount++
            }

            if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
                Write-Log "Service still exists after uninstall (may be marked for deletion)" "WARN"
            } else {
                Write-Log "Service $serviceName uninstalled successfully" "SUCCESS"
            }

            # Remove service executable
            if (Test-Path $serviceExe) {
                Remove-Item $serviceExe -Force
                Write-Log "Removed service executable" "INFO"
            }
        } catch {
            Write-Log "Failed to uninstall service: $_" "ERROR"
            throw
        }
    } else {
        Write-Log "Service executable not found: $serviceExe" "WARN"
        Write-Log "Service may have been manually removed" "WARN"
    }
}

function Remove-ServiceLogs {
    param(
        [hashtable]$ServiceConfig
    )

    $centralLogDir = "$env:ProgramData\Dr.Migrate\llm"
    $serviceName = $ServiceConfig.Name

    # Remove centralized log files for this specific service
    if (Test-Path $centralLogDir) {
        $serviceLogFiles = Get-ChildItem -Path $centralLogDir -Filter "$serviceName*.log" -File
        if ($serviceLogFiles.Count -gt 0) {
            Write-Log "Removing $($serviceLogFiles.Count) log files for $serviceName from $centralLogDir" "INFO"
            try {
                $serviceLogFiles | Remove-Item -Force
                Write-Log "Log files removed successfully" "SUCCESS"
            } catch {
                Write-Log "Failed to remove log files: $_" "WARN"
            }
        } else {
            Write-Log "No log files found for $serviceName in $centralLogDir" "INFO"
        }

        # Check if centralized log directory is now empty and can be removed
        $remainingLogs = Get-ChildItem -Path $centralLogDir -File -ErrorAction SilentlyContinue
        if (-not $remainingLogs) {
            Write-Log "Centralized log directory is empty. Removing directory." "INFO"
            try {
                Remove-Item -Path $centralLogDir -Force -Recurse
                Write-Log "Centralized log directory removed" "SUCCESS"
            } catch {
                Write-Log "Failed to remove centralized log directory: $_" "WARN"
            }
        }
    } else {
        Write-Log "Centralized log directory not found: $centralLogDir" "INFO"
    }

    # Also check and clean legacy service-specific log directories (migration cleanup)
    $legacyLogDir = Join-Path $ServiceConfig.WorkingDir "logs"
    if (Test-Path $legacyLogDir) {
        Write-Log "Found legacy log directory: $legacyLogDir" "INFO"
        $legacyLogFiles = Get-ChildItem -Path $legacyLogDir -File -ErrorAction SilentlyContinue
        if ($legacyLogFiles) {
            Write-Log "Removing $($legacyLogFiles.Count) legacy log files" "INFO"
            try {
                Remove-Item -Path "$legacyLogDir\*" -Force
                Remove-Item -Path $legacyLogDir -Force
                Write-Log "Legacy log directory cleaned up" "SUCCESS"
            } catch {
                Write-Log "Failed to clean legacy logs: $_" "WARN"
            }
        }
    }
}

# Main execution
try {
    Write-Log "=== Dr.Migrate Assistant Services Uninstallation ===" "INFO"

    # Verify administrator privileges
    if (-not (Test-Administrator)) {
        Write-Log "This script must be run as Administrator" "ERROR"
        exit 1
    }

    # Determine which services to uninstall
    $servicesToUninstall = @()
    switch ($ServiceName.ToLower()) {
        'all' {
            # Uninstall in reverse dependency order: copilotkit first
            $servicesToUninstall = @('copilotkit', 'agents')
        }
        'agents' {
            $servicesToUninstall = @('agents')

            # Dependency warning
            $copilotService = Get-Service -Name "DrMigrate-CopilotKitProxy" -ErrorAction SilentlyContinue
            if ($copilotService -and -not $Force) {
                Write-Log "" "WARN"
                Write-Log "WARNING: CopilotKit depends on AgentsServer" "WARN"
                Write-Log "CopilotKit is currently installed and will break if AgentsServer is removed" "WARN"
                Write-Log "" "INFO"
                Write-Log "Recommendations:" "INFO"
                Write-Log "  - Uninstall both: .\uninstall-services.ps1" "INFO"
                Write-Log "  - Uninstall CopilotKit first: .\uninstall-services.ps1 -ServiceName copilotkit" "INFO"
                Write-Log "  - Force uninstall: .\uninstall-services.ps1 -ServiceName agents -Force" "INFO"
                Write-Log "" "INFO"

                $continue = Read-Host "Continue uninstalling AgentsServer only? (y/N)"
                if ($continue -ne 'y' -and $continue -ne 'Y') {
                    Write-Log "Uninstallation cancelled by user" "INFO"
                    exit 0
                }
            }
        }
        'copilotkit' {
            $servicesToUninstall = @('copilotkit')
        }
    }

    Write-Log "Services to uninstall: $($servicesToUninstall -join ', ')" "INFO"

    # Confirmation prompt (unless -Force specified)
    if (-not $Force) {
        Write-Host ""
        Write-Host "This will uninstall the following services:" -ForegroundColor Yellow
        foreach ($svcKey in $servicesToUninstall) {
            Write-Host "  - $($AllServices[$svcKey].DisplayName)" -ForegroundColor Yellow
        }
        Write-Host ""

        if (-not $KeepLogs) {
            Write-Host "Log files will be DELETED." -ForegroundColor Yellow
            Write-Host "Use -KeepLogs to preserve them." -ForegroundColor Yellow
        } else {
            Write-Host "Log files will be preserved." -ForegroundColor Green
        }

        Write-Host ""
        $confirm = Read-Host "Continue? (y/N)"
        if ($confirm -ne 'y' -and $confirm -ne 'Y') {
            Write-Log "Uninstallation cancelled by user" "INFO"
            exit 0
        }
    }

    # Uninstall services
    foreach ($svcKey in $servicesToUninstall) {
        Uninstall-Service -ServiceConfig $AllServices[$svcKey]
    }

    # Remove logs (unless -KeepLogs specified)
    if (-not $KeepLogs) {
        Write-Log "" "INFO"
        Write-Log "Cleaning up log files..." "INFO"
        foreach ($svcKey in $servicesToUninstall) {
            Remove-ServiceLogs -ServiceConfig $AllServices[$svcKey]
        }
    }

    # Clean up WinSW executable (only if uninstalling all services)
    if ($ServiceName -eq 'all') {
        $winswPath = Join-Path $ScriptRoot "WinSW.NET461.exe"
        if (Test-Path $winswPath) {
            Write-Log "Removing WinSW executable" "INFO"
            Remove-Item $winswPath -Force
        }
    }

    Write-Log "" "INFO"
    Write-Log "Uninstallation completed successfully!" "SUCCESS"

    # Verify services are removed
    Write-Log "" "INFO"
    Write-Log "Verification:" "INFO"
    foreach ($svcKey in $servicesToUninstall) {
        $service = $AllServices[$svcKey]
        $svc = Get-Service -Name $service.Name -ErrorAction SilentlyContinue
        if ($svc) {
            Write-Log "  $($service.DisplayName): STILL EXISTS (manual cleanup required)" "WARN"
        } else {
            Write-Log "  $($service.DisplayName): Removed successfully" "SUCCESS"
        }
    }

} catch {
    Write-Log "Uninstallation failed: $_" "ERROR"
    exit 1
}

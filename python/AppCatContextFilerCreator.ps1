param(
    [string]$MigrationInfo,
    [string]$ScriptFile,
    [pscustomobject]$Parameters,
    [string]$AppGuid,
    [string]$Technology,
    [string]$ScriptExecutionId

)

#Set Required script path
$RefPath = (Get-Location).Path
Push-Location -Path  $RefPath -StackName "refpath"
Set-Location $PSScriptRoot
Import-module ..\..\L3AzureMigrateAgentless -Force

if(!$MigrationInfo){
    $MigrationInfo = Get-ChildItem -path ..\..\ -Filter "*.json" | Where-Object { $_.Name -like "*_MigrationInfo.json" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}
#Import Module

Import-Module ..\..\L3AzureAssessment\L3AzureAssessment.psm1 -Force
Import-Module ..\..\L3AzureMigrate -Force
Import-module ..\..\L3SharedFunctions -Force 

Function Execute-DatabaseQuery {
    param(
        [string]$SQLServer = "$($Env:COMPUTERNAME)",
        [string]$Database = 'Assessments',
        [string]$Query
    )

    try {
        Import-Module sqlserver -force

        #Write-Log -Message "[$((get-date).TimeOfDay.ToString()) INFO ] Executing database sql query $($Query)" -LogType INFO

        $Result = Invoke-Sqlcmd -ServerInstance $SqlServer -Database $Database -Query $Query
        return $Result
    }
    Catch {
        $ErrorMessage = $_ -replace "\n", ""
        
        Write-Log -Message "[$((get-date).TimeOfDay.ToString()) ERROR ] Function Execute-DatabaseQuery $ErrorMessage" -LogType ERROR
    }
}

Function Update-ScriptExecutionProgressToDB {
    param(
        [string]$LastEditBy = $Global:__CurrentUserName__,
        [datetime]$LastEditTimeStamp = (Get-Date),
        [bool]$IsDeleted = $false,
        [double]$percentage,
        [string]$status,
        [string]$details
    )

    $UpdateScriptExecutionQuery = @"
	UPDATE [ASSESSMENTS].[DBO].[ScriptExecutions] 
	SET LAST_EDIT_BY = '$($LastEditBy)',
	LAST_EDIT_TIMESTAMP = '$($LastEditTimeStamp)', 
	IS_DELETED = '$($IsDeleted)', 
	PERCENTAGE = $percentage,
	STATUS = '$($status)',
	DETAILS = '$($details)'
	WHERE ID = '$($ScriptExecutionId)'
"@

    Execute-DatabaseQuery -SQLServer "$($Env:COMPUTERNAME)" -Query $UpdateScriptExecutionQuery
    Write-Log -Message "[$((get-date).TimeOfDay.ToString()) INFORMATION ] DrMigrate AppCatContextFilerCreator Progress Percentage: $percentage, Details: $details ID: $ScriptExecutionId" -LogType INFO  
}


if(!$ScriptFile){
    $ScriptFile = "..\..\L3Python\Analysis\app_cat_context_file_generator.py"
    $ScriptFileFullPath = Get-ChildItem $ScriptFile
}


$Date = (Get-Date).ToString("ddMMyyyy")
$PythonDir = "$($env:ALLUSERSPROFILE)\Dr.Migrate\PythonLogs"
if(!(Test-Path $PythonDir -PathType Container)){
    New-Item "$($env:ALLUSERSPROFILE)\Dr.Migrate\PythonLogs" -ItemType Directory -Force | Out-Null
}
$FilePath = (join-path $PythonDir "DrMigrate_AppCatContextFilerCreator_$($Date).log")

$Parameters = [PSCustomObject]@{'appGuid' = $($AppGuid)
                                'technology' = $($Technology)
                                'scriptExecutionId' = $($ScriptExecutionId)
                            }


if ([string]::IsNullOrEmpty($AppGuid) -Or [string]::IsNullOrEmpty($ScriptExecutionId)) {

    Write-Verbose "[$((get-date).TimeOfDay.ToString()) ERROR ] AppCatContextFilerCreator failed due to missing required input parameter."
    Write-Log -Message "[$((get-date).TimeOfDay.ToString()) ERROR ] AppCatContextFilerCreator failed due to missing required input parameter." -LogType ERROR
    $Details = "DrMigrate was unable to run AppCatContextFilerCreator due to error PY_PARAM_001_ERROR. Please contact Dr Migrate support stating the error code to get this issue resolved."
    Update-ScriptExecutionProgressToDB -percentage 100 -status "Failed" -details $Details -id $ScriptExecutionId
}
else{
    Invoke-PythonScript -ScriptFile $ScriptFileFullPath.FullName  -parameters $Parameters -ScriptTask 'AppCatContextFilerCreator' -FilePath $FilePath -Encoding UTF8
}

#Release path
Pop-Location -StackName "refpath"
$Global:__MigrationInfo__ = $null
<#
.SYNOPSIS
    Launches multiple simulated log generators and log shipping agents in separate PowerShell terminals.

.EXAMPLE
    .\agent\start_agents.ps1
    .\agent\start_agents.ps1 -Sources @("server-1", "server-2", "server-3") -Interval 2
#>

param(
    [string[]]$Sources = @("server-1", "server-2", "server-3"),
    [float]$Interval = 2.0
)

$WorkspaceRoot = (Get-Item $PSScriptRoot).Parent.FullName
$PythonExe = Join-Path $WorkspaceRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Group9 Log Aggregator: Multi-Agent Simulator" -ForegroundColor Cyan
Write-Host " Workspace : $WorkspaceRoot" -ForegroundColor DarkGray
Write-Host " Python    : $PythonExe" -ForegroundColor DarkGray
Write-Host " Sources   : $($Sources -join ', ')" -ForegroundColor Yellow
Write-Host " Interval  : ${Interval}s" -ForegroundColor DarkGray
Write-Host "==========================================================" -ForegroundColor Cyan

# Create logs directory if not exists
$LogsDir = Join-Path $WorkspaceRoot "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

foreach ($src in $Sources) {
    Write-Host "[+] Launching Generator for $src..." -ForegroundColor Green
    $genTitle = "Generator - $src"
    $genCmd = "`$Host.UI.RawUI.WindowTitle = '$genTitle'; cd '$WorkspaceRoot'; & '$PythonExe' -m agent.generator --source $src --interval $Interval"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $genCmd

    Write-Host "[+] Launching Shipping Agent for $src..." -ForegroundColor Green
    $agentTitle = "Shipper Agent - $src"
    $agentCmd = "`$Host.UI.RawUI.WindowTitle = '$agentTitle'; cd '$WorkspaceRoot'; & '$PythonExe' -m agent.agent --source $src --poll-interval 1.0"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $agentCmd
}

Write-Host "`nAll simulated agents started in dedicated PowerShell windows." -ForegroundColor Green
Write-Host "Monitor ingestion in the API Swagger UI: http://127.0.0.1:8000/docs" -ForegroundColor Cyan

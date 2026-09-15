# scripts/run_pipeline.ps1
# Script PowerShell para ejecución periódica automatizada del Pipeline de Motos AI Leads.
# Compatible con Windows Task Scheduler (Programador de Tareas de Windows).

param (
    [switch]$DryRun,
    [string]$InboxDir = "data/inbox",
    [string]$ArchiveDir = "data/processed"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -Path $ProjectRoot

# Detectar intérprete de Python en el entorno virtual
$PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

$ArgsList = @("scripts/run_pipeline.py", "--inbox-dir", $InboxDir, "--archive-dir", $ArchiveDir)
if ($DryRun) {
    $ArgsList += "--dry-run"
}

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Iniciando Pipeline de Motos AI Leads..." -ForegroundColor Cyan
Write-Host "Proyecto: $ProjectRoot" -ForegroundColor Gray
Write-Host "Ejecutable: $PythonExe" -ForegroundColor Gray
Write-Host "Argumentos: $($ArgsList -join ' ')" -ForegroundColor Gray
Write-Host "==========================================================================" -ForegroundColor Cyan

& $PythonExe @ArgsList
$ExitCode = $LASTEXITCODE

if ($ExitCode -eq 0) {
    Write-Host "`nPipeline ejecutado exitosamente." -ForegroundColor Green
} else {
    Write-Host "`nError en la ejecución del Pipeline (Código de salida: $ExitCode)." -ForegroundColor Red
}

exit $ExitCode

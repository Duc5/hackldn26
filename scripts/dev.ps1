param(
    [switch]$NoMongo
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

function Start-Proc($name, $filePath, $args, $workingDir, $envVars) {
    foreach ($key in $envVars.Keys) {
        [Environment]::SetEnvironmentVariable($key, $envVars[$key], "Process")
    }
    $proc = Start-Process -FilePath $filePath -ArgumentList $args -WorkingDirectory $workingDir -PassThru
    Write-Host "$name PID=$($proc.Id)"
    return $proc
}

if (-not $NoMongo) {
    try {
        Start-Proc "MongoDB" "mongod" @("--dbpath", ".mongo-data") $root @{} | Out-Null
    }
    catch {
        Write-Warning "Could not start mongod automatically. Start MongoDB manually or run: .\scripts\dev.ps1 -NoMongo"
    }
}

Start-Proc "Backend" "python" @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000") $backendDir @{} | Out-Null
Start-Proc "Frontend" "npm.cmd" @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") $frontendDir @{} | Out-Null

Write-Host ""
Write-Host "Backend:  http://127.0.0.1:8000/docs"
Write-Host "Frontend: http://127.0.0.1:5173"

# Installs the plant-floor Streamlit server on a Windows machine. Run once, as Administrator:
#
#     powershell -ExecutionPolicy Bypass -File planta_local\install_service.ps1
#
# 1. Creates a Python virtual environment in planta_local\.venv and installs requirements.txt
# 2. Opens TCP ports 8500-8503 in Windows Firewall (domain/private networks)
# 3. Registers a scheduled task that starts planta_server.py at boot (no user needs to log in)
#    and restarts it if it stops
#
# Requires Python 3.11+ on PATH ("py" launcher or "python") and cognite-sdk\.env with the CDF
# service-account credentials (see env.example).

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$venv = Join-Path $here ".venv"
$taskName = "Planta - Servidor Streamlit"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Ejecuta este script como Administrador."
}
if (-not (Test-Path (Join-Path $root ".env"))) {
    throw "Falta $root\.env con las credenciales de CDF (copia env.example y complétalo)."
}

Write-Host "1/3 Entorno de Python..."
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv $venv } else { python -m venv $venv }
}
$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install --upgrade pip | Out-Null
& $python -m pip install -r (Join-Path $here "requirements.txt")

Write-Host "2/3 Firewall (puertos 8500-8503)..."
if (-not (Get-NetFirewallRule -DisplayName "Planta Streamlit" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Planta Streamlit" -Direction Inbound -Protocol TCP `
        -LocalPort 8500-8503 -Action Allow -Profile Domain,Private | Out-Null
}

Write-Host "3/3 Tarea programada '$taskName'..."
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$(Join-Path $here 'planta_server.py')`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
       Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "Listo. En 1-2 minutos estaran disponibles:"
Write-Host "  TV (rotacion L1/L3):     http://${ip}:8500/tv.html"
Write-Host "  Linea 1 - Vista Planta:  http://${ip}:8501"
Write-Host "  Linea 3 - Vista Planta:  http://${ip}:8502"
Write-Host "  Reporte de Produccion:   http://${ip}:8503"
Write-Host "Logs: $here\logs"

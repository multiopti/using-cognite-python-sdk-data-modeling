# Removes what install_service.ps1 set up (scheduled task + firewall rule). Run as Administrator.
# The .venv and logs folders are left in place; delete them by hand if no longer needed.
$taskName = "Planta - Servidor Streamlit"
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "planta_server.py|run_app.py" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Remove-NetFirewallRule -DisplayName "Planta Streamlit" -ErrorAction SilentlyContinue
Write-Host "Servidor de planta desinstalado."

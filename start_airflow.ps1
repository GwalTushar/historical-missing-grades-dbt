# Start Airflow locally
$ProjectDir = "C:\Users\TusharGwal\Documents\shopstream_dbt_demo"
$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$env:AIRFLOW_HOME = Join-Path $ProjectDir "airflow"

Write-Host "Starting Airflow Webserver on http://localhost:8080" -ForegroundColor Cyan
Write-Host "Login: admin / admin123" -ForegroundColor Yellow
Write-Host ""

$webserver = Start-Job -ScriptBlock {
    param($airflowHome, $pythonExe)
    $env:AIRFLOW_HOME = $airflowHome
    & $pythonExe -m airflow webserver --port 8080
} -ArgumentList $env:AIRFLOW_HOME, $PythonExe

$scheduler = Start-Job -ScriptBlock {
    param($airflowHome, $pythonExe)
    $env:AIRFLOW_HOME = $airflowHome
    & $pythonExe -m airflow scheduler
} -ArgumentList $env:AIRFLOW_HOME, $PythonExe

Write-Host "Airflow started! Press Ctrl+C to stop." -ForegroundColor Green
Write-Host "Webserver Job ID: $($webserver.Id)" -ForegroundColor Gray
Write-Host "Scheduler Job ID: $($scheduler.Id)" -ForegroundColor Gray

try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    Write-Host "`nStopping Airflow..." -ForegroundColor Yellow
    Stop-Job -Job $webserver, $scheduler
    Remove-Job -Job $webserver, $scheduler
}

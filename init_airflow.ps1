$ErrorActionPreference = "Stop"

$ProjectDir = "C:\Users\TusharGwal\Documents\shopstream_dbt_demo"
$AirflowHome = Join-Path $ProjectDir "airflow"
$AirflowVersion = "2.10.0"

Set-Location $ProjectDir
$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"

$PythonVersion = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
$ConstraintUrl = "https://raw.githubusercontent.com/apache/airflow/constraints-$AirflowVersion/constraints-$PythonVersion.txt"

Write-Host "Installing Airflow $AirflowVersion with Python $PythonVersion constraints..." -ForegroundColor Cyan
& $PythonExe -m pip install "apache-airflow==$AirflowVersion" --constraint $ConstraintUrl

$env:AIRFLOW_HOME = $AirflowHome
$env:AIRFLOW__CORE__DAGS_FOLDER = Join-Path $AirflowHome "dags"
$env:AIRFLOW__CORE__LOAD_EXAMPLES = "False"
$env:AIRFLOW__WEBSERVER__WEB_SERVER_PORT = "8080"

Write-Host "Initializing Airflow database..." -ForegroundColor Cyan
& $PythonExe -m airflow db init

Write-Host "Creating or updating admin user..." -ForegroundColor Cyan
try {
    & $PythonExe -m airflow users create `
        --username admin `
        --firstname Tushar `
        --lastname Gwal `
        --role Admin `
        --email tushar@example.com `
        --password admin123
}
catch {
    Write-Host "Admin user may already exist; continuing." -ForegroundColor Yellow
}

Write-Host "Airflow initialized. Login: admin / admin123" -ForegroundColor Green

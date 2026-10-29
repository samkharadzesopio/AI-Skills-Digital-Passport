param([string]$Python)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $Python = Join-Path (Split-Path -Parent $projectRoot) 'AI-Skills-Digital-Passport\.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $Python)) { throw 'Supply -Python with the existing virtual environment python.exe.' }
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source
$vitePath = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $vitePath)) { throw 'Run npm.cmd ci in frontend first.' }
foreach ($localPort in @(8000, 5173)) {
    $connection = Get-NetTCPConnection -LocalPort $localPort -State Listen -ErrorAction SilentlyContinue
    if ($connection) { throw "Port $localPort is already in use. Stop the old development server before starting this worktree." }
}
$env:BTU_LOCAL_DEVELOPMENT = '1'
$env:DJANGO_SETTINGS_MODULE = 'config.local_dev_settings'
$env:VITE_ENABLE_DEMO = 'false'
$env:BTU_DEV_API_TARGET = 'http://127.0.0.1:8000'
$managePath = Join-Path $projectRoot 'backend\manage.py'
& $Python $managePath check
if ($LASTEXITCODE -ne 0) { throw 'Local Django configuration check failed.' }
& $Python $managePath migrate --check
if ($LASTEXITCODE -ne 0) { throw 'Local database is unavailable or has pending migrations. Review it before migrating.' }
$logDirectory = Join-Path $projectRoot 'backend\.local-run'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$backendProcess = Start-Process -FilePath $Python -ArgumentList @('-u', ('"' + $managePath + '"'), 'runserver', '127.0.0.1:8000', '--noreload') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'django.out.log') -RedirectStandardError (Join-Path $logDirectory 'django.err.log') -PassThru
$frontendProcess = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $vitePath + '"'), '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'vite.out.log') -RedirectStandardError (Join-Path $logDirectory 'vite.err.log') -PassThru
@{ backend = $backendProcess.Id; frontend = $frontendProcess.Id } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logDirectory 'processes.json')
foreach ($healthUrl in @('http://127.0.0.1:8000/api/accounts/csrf/', 'http://127.0.0.1:5173/api/accounts/csrf/')) {
    $ready = $false
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        try { $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 1; $ready = $response.StatusCode -eq 200 } catch { $ready = $false }
        if ($ready) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "Local service did not become ready at $healthUrl. Inspect backend/.local-run logs." }
}
Write-Output "Django PID $($backendProcess.Id): http://127.0.0.1:8000/"
Write-Output "Vite PID $($frontendProcess.Id): http://127.0.0.1:5173/student/login"
Write-Output "Local OTP email files: $(Join-Path $projectRoot 'backend\.local-mail')"

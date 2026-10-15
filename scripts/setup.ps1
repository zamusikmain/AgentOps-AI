$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Install Python 3.11+ for the backend. Node.js 20.9+ is also required.' }
# --without-pip avoids the ensurepip failure observed in some Windows Python installs.
python -m venv --without-pip backend/.venv
if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python venv.' }
python -m pip --python backend/.venv/Scripts/python.exe install -r backend/requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed. Check Python pip and network access.' }
npm ci --no-audit
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
Push-Location backend
try {
    ./.venv/Scripts/python.exe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
} finally { Pop-Location }
Write-Host 'Ready. Existing backend/.env was preserved. Run scripts/start-backend.ps1 and scripts/start-frontend.ps1 in separate terminals.'

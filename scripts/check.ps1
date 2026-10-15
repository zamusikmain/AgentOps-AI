$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
Push-Location backend
try {
    New-Item -ItemType Directory -Force '.pytest-work' | Out-Null
    $testDirectory = Join-Path '.pytest-work' ([guid]::NewGuid().ToString())
    ./.venv/Scripts/python.exe -m pytest -q --basetemp=$testDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
} finally { Pop-Location }
foreach ($taskName in @('typecheck', 'test', 'build')) {
    npm run $taskName
    if ($LASTEXITCODE -ne 0) { throw "$taskName failed." }
}

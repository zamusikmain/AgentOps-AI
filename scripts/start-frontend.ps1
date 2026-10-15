$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:NEXT_TELEMETRY_DISABLED = '1'
npm run dev

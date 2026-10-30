param([int]$Port = 8000, [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $localPython)) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    & $localPython -c "import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(name) is not None for name in ['fastapi', 'uvicorn', 'pandas', 'numpy', 'sklearn', 'httpx']) else 1)"
    if ($LASTEXITCODE -ne 0) {
        & $localPython -m pip install -r requirements-local.txt
        if ($LASTEXITCODE -ne 0) { throw 'Could not install Python dependencies.' }
    }
    if (-not $SkipBuild) {
        Push-Location frontend
        try {
            if (-not (Test-Path -LiteralPath node_modules)) {
                npm.cmd ci
                if ($LASTEXITCODE -ne 0) { throw 'Could not install frontend dependencies.' }
            }
            npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
        } finally { Pop-Location }
    }
    Write-Host "Indian Market Lab: http://127.0.0.1:$Port/analyze"
    Write-Host 'Historical daily research. No broker account or API keys required.'
    & $localPython -m uvicorn app.local_main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'The local analysis server could not start.' }
} finally { Pop-Location }

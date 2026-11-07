$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath (Join-Path $projectRoot 'backend')
uv sync --frozen
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency setup failed' }
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
Set-Location -LiteralPath (Join-Path $projectRoot 'frontend')
npm ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency setup failed' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
Set-Location -LiteralPath (Join-Path $projectRoot 'backend')
uv run uvicorn app.main:app --host 127.0.0.1 --port 8787 --no-access-log

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $projectRoot
docker version
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop first' }
foreach ($image in @('semgrep/semgrep:1.184.0', 'ghcr.io/google/osv-scanner:v2.7.0', 'aquasec/trivy:0.76.2')) {
    docker pull $image
    if ($LASTEXITCODE -ne 0) { throw "Scanner installation failed: $image" }
}
docker build -t kyro-sandbox:local -f infrastructure/docker/Sandbox.Dockerfile .
if ($LASTEXITCODE -ne 0) { throw 'Sandbox image build failed' }

param(
    [Parameter(Mandatory=$true)][string]$ModelPath,
    [string]$ServerPath = "$PSScriptRoot/../../tools/bin/llama/llama-server.exe",
    [int]$Port = 8080
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ModelPath -PathType Leaf)) { throw 'GGUF file not found; specify your existing model file.' }
if (-not (Test-Path -LiteralPath $ServerPath -PathType Leaf)) { throw 'llama-server missing. Install official llama.cpp binaries or run python tools/install_llama.py.' }
& $ServerPath --model $ModelPath --alias qwen3-8b --host 127.0.0.1 --port $Port --ctx-size 8192 --parallel 1 --gpu-layers auto --cache-type-k q8_0 --cache-type-v q8_0 --batch-size 256 --ubatch-size 128 --reasoning on --reasoning-budget 1024 --no-webui --cors-origins localhost --no-cors-credentials --sleep-idle-seconds 60 --metrics
if ($LASTEXITCODE -ne 0) { throw "llama-server exited with $LASTEXITCODE" }

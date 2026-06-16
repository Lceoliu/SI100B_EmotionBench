$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Remote = $env:EMOTION_BENCH_REMOTE
if (-not $Remote) { $Remote = "li@10.19.138.116" }

$RemoteRoot = $env:EMOTION_BENCH_REMOTE_ROOT
if (-not $RemoteRoot) { $RemoteRoot = "/home/SI100B_26Fall/emotion-bench" }

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptRoot "..")
$FrontendRoot = Join-Path $ProjectRoot "frontend"

Push-Location $FrontendRoot
try {
  npm run build
} finally {
  Pop-Location
}

scp -r "$FrontendRoot/src" "${Remote}:${RemoteRoot}/frontend/"
scp -r "$FrontendRoot/dist" "${Remote}:${RemoteRoot}/frontend/"
ssh $Remote "cd $RemoteRoot && docker compose restart web && curl -fsS http://127.0.0.1:`${WEB_PORT:-18080}/health"

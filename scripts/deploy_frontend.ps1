$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Set these in your shell or PowerShell profile, e.g.
#   $env:EMOTION_BENCH_REMOTE = "user@bench-server"
#   $env:EMOTION_BENCH_REMOTE_ROOT = "/srv/emotion-bench"
$Remote = $env:EMOTION_BENCH_REMOTE
if (-not $Remote) { throw "Set EMOTION_BENCH_REMOTE to the SSH target, e.g. user@bench-server." }

$RemoteRoot = $env:EMOTION_BENCH_REMOTE_ROOT
if (-not $RemoteRoot) { throw "Set EMOTION_BENCH_REMOTE_ROOT to the checkout path on the server." }

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

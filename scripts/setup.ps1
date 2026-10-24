# ShopPilot local bootstrap (Windows PowerShell)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> Docker: Postgres + Redis"
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
  docker compose up -d db redis
} else {
  Write-Host "WARNING: docker not found. Start Postgres (5432) + Redis (6379) yourself,"
  Write-Host "  or install Docker Desktop and re-run this script."
  Write-Host "  Seed will fail until DATABASE_URL is reachable."
}

Write-Host "==> Backend .env"
if (-not (Test-Path "backend\.env")) {
  Copy-Item "backend\.env.example" "backend\.env"
  Write-Host "Created backend\.env from example"
}
# Ensure webhook verify token exists for Meta handshake in local/dev
$envText = Get-Content "backend\.env" -Raw
if ($envText -notmatch "META_WEBHOOK_VERIFY_TOKEN=") {
  Add-Content "backend\.env" "`nMETA_WEBHOOK_VERIFY_TOKEN=shoppilot-dev-verify"
}

Write-Host "==> Frontend .env"
if (-not (Test-Path "frontend\.env")) {
  Copy-Item "frontend\.env.example" "frontend\.env"
  Write-Host "Created frontend\.env from example"
}

Write-Host "==> Python venv + deps"
Set-Location "$Root\backend"
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -q -r requirements-dev.txt

Write-Host "==> Schema + demo seed"
& .\.venv\Scripts\python.exe -m app.initial_data

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  Backend:  cd backend; .\.venv\Scripts\python.exe -m app.main"
Write-Host "  Frontend: cd frontend; npm install; npm run dev"
Write-Host "  Login:    owner@demo-shop.test / ChangeMe123!"
Write-Host "  Optional: fill API keys in backend\.env (see .env.example)"

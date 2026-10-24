#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Docker: Postgres + Redis"
if command -v docker >/dev/null 2>&1; then
  docker compose up -d db redis
else
  echo "WARNING: docker not found. Start Postgres (5432) + Redis (6379) yourself,"
  echo "  or install Docker and re-run. Seed will fail until DATABASE_URL is reachable."
fi

echo "==> Backend .env"
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from example"
fi
if ! grep -q '^META_WEBHOOK_VERIFY_TOKEN=' backend/.env 2>/dev/null; then
  echo "META_WEBHOOK_VERIFY_TOKEN=shoppilot-dev-verify" >> backend/.env
fi

echo "==> Frontend .env"
if [ ! -f frontend/.env ]; then
  cp frontend/.env.example frontend/.env
  echo "Created frontend/.env from example"
fi

echo "==> Python venv + deps"
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements-dev.txt

echo "==> Schema + demo seed"
python -m app.initial_data

echo ""
echo "Done. Next:"
echo "  Backend:  cd backend && .venv/bin/python -m app.main"
echo "  Frontend: cd frontend && npm install && npm run dev"
echo "  Login:    owner@demo-shop.test / ChangeMe123!"
echo "  Optional: fill API keys in backend/.env (see .env.example)"

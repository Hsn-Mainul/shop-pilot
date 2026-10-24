# ShopPilot — Shop Automation Platform

SRS-aligned merchant console (React) + FastAPI backend for Bangladesh social commerce shops.

## Quick start

**Windows**
```powershell
.\scripts\setup.ps1
cd backend; .\.venv\Scripts\python.exe -m app.main
# other terminal
cd frontend; npm install; npm run dev
```

**macOS / Linux**
```bash
chmod +x scripts/setup.sh && ./scripts/setup.sh
cd backend && .venv/bin/python -m app.main
# other terminal
cd frontend && npm install && npm run dev
```

- App: http://localhost:5175  
- API docs: http://localhost:8001/docs  
- Demo login: `owner@demo-shop.test` / `ChangeMe123!`

## Optional provider credentials

Core shop flows (orders, products, inbox, finance, documents, automations) work **without** external keys.

Copy keys into `backend/.env` only when you want live features:

| Env vars | Enables |
|---|---|
| `LLM_API_KEY` | AI answers, TTS, shift LLM nudge |
| `ASR_API_KEY` | Voice transcription + call media-stream ASR |
| `TWILIO_*` + `PUBLIC_BASE_URL` | Real outbound calls / SMS / WhatsApp |
| `SMTP_*` | Invite + campaign email |
| `META_*` | Facebook OAuth + catalogue sync + publish |
| `GOOGLE_*` / `STRIPE_*` | Google / Stripe OAuth |
| `REDIS_URL` | Celery jobs + multi-worker WebSockets |

Check readiness anytime: `GET /api/v1/system/providers` (also on Setup in the UI).

## Repo layout

- `frontend/` — Vite React merchant console  
- `backend/` — FastAPI API, Celery workers, integrations  
- `docker-compose.yml` — Postgres, Redis, optional API/worker/beat  

See `backend/README.md` and `frontend/README.md` for module details.

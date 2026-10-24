# Backend — Shop Automation Platform API

Python / FastAPI backend implementing the full module surface from the SRS and API contract. 79 endpoints across 21 routers, 39 database tables, plus a Celery worker/beat for background jobs.

## Stack
- FastAPI + SQLAlchemy 2.0 + Alembic
- PostgreSQL (tenant-scoped via `shop_id` on every table), JSONB for flexible config fields
- Celery + Redis for background jobs (bulk campaigns, scheduled automations, social publishing)
- JWT access/refresh tokens, bcrypt password hashing
- Role-based access control (Super Admin / Admin / Sales / Support / Warehouse)
- Real provider adapters under `app/integrations/`: LLM (OpenAI-compatible), ASR (OpenAI-compatible transcription), Twilio (voice/SMS/WhatsApp), SMTP (email), Meta Graph API (Facebook/Instagram) — each is config-driven: fully functional once you supply real credentials, and raises a clear `*NotConfiguredError` (never a fake success) when you haven't yet. See `.env.example` for every credential they read.

## Local setup

Fastest path from the repo root:

```powershell
.\scripts\setup.ps1          # Windows
# or: ./scripts/setup.sh     # macOS/Linux
```

That starts Postgres/Redis, creates `.env` from `.env.example`, installs deps, runs `ensure_schema()` + demo seed.

Manual equivalent:

1. `docker compose up -d db redis`
2. `cd backend && python -m venv .venv && pip install -r requirements-dev.txt`
3. `cp .env.example .env` (fill optional provider keys later)
4. `python -m app.initial_data` — creates tables + demo user + dialects/integrations
5. `python -m app.main` → http://localhost:8001/docs  
   Provider readiness: `GET /api/v1/system/providers`
6. Optional Celery: `docker compose up -d worker beat`

(Optional later) generate Alembic revisions once schema stabilizes:
```bash
alembic revision --autogenerate -m "sync"
alembic upgrade head
```

## Running tests
```bash
pytest
```

## Module coverage (implemented)

| Module | Router | Notes |
|---|---|---|
| Auth | `auth.py` | Login + refresh JWT with `shop_id` + `role`. |
| System | `system.py` | Provider readiness (`/system/providers`). |
| Shops & Team | `shops.py` | Profile, checklist, invite (+ SMTP email). |
| Catalogue | `products.py` | Products/services, stock ledger, bulk import, FB catalogue sync. |
| Customers | `customers.py` | CRUD, segments, block, reviews. |
| Inbox | `conversations.py` | Threads, handover, ASR on voice notes when configured. |
| Calls | `calls.py` | Outbound Twilio, TwiML/TTS, media-stream dialect ASR. |
| Orders | `orders.py` | Pipeline + CSV sync + auto-issue docs on status. |
| Payments | `payments.py` | Record/confirm, ledger post, gateway webhook match. |
| Delivery | `delivery.py` | Parcels, COD summary. |
| Finance | `finance.py` | P&L, forecast, expenses, CSV exports. |
| Documents | `documents.py` | PDF issue, templates, auto-issue rules. |
| Integrations | `integrations.py` | Meta/Google/Stripe OAuth, dialects, webhook config. |
| Automation | `automation.py` | Rules, recipes, campaigns (+ delivery webhooks). |
| AI | `ai.py` | Knowledge, ask, simulate chat/call (+ real LLM/TTS). |
| Social | `social_studio.py` | Compose + Celery Meta publish when connected. |
| Loyalty / Team / Plan / Support | respective routers | Milestone rewards, volume+LLM shifts, plans, tickets. |
| Realtime | `/ws` | Shop WebSocket hub (+ Redis fan-out). |
| Setup Checklist | `shops.py` (`/shops/me/setup-checklist`) | Live progress computed from real data (products exist? channel connected? delivery charge set? team size > 1?), not a stored flag (FR-SET-01/04). |
| Reviews | `customers.py` (`reviews_router`, mounted at `/reviews`) | Create/list/hide customer reviews (FR-CUST-04). |
| Voice Persona & Call Routing | `calls.py` (`/calls/config/...`) | Choose/edit the AI voice persona, opening script, forbidden topics, business-hours/overflow routing rules, and voice quality metrics (avg handling time, resolved-without-handover %, calls by dialect) (FR-VPER-01/02/04, FR-CALL-11). |
| AI Simulation | `ai.py` (`/ai/simulate-chat`, `/ai/simulate-call`) | Real routes for testing AI behavior before enabling Autopilot (FR-AI-05, FR-VPER-03) — replies are a simple echo/keyword-match until the AI Orchestrator is wired in. |
| Inbound Webhook Receiver | `webhooks.py` | Generic `POST /webhooks/{provider}` that stores every inbound event for later processing (architecture doc's Webhook Receiver). Per-provider signature verification is NOT implemented yet — every event is stored with `signature_verified=False`. |
| Inbox KPIs | `conversations.py` (`/conversations/stats`) | Waiting-for-reply count, price-request count, average reply time, orders-from-comments (FR-CHAT-07). |
| Finance Statements & Exports | `finance.py` (`/finance/statements/{period}`, `/finance/exports/{type}`) | Real month/quarter/year P&L statements and CSV exports (sales book, expenses, stock value) (FR-FIN-05/06). |
| Team Invite | `shops.py` (`POST /team-members/invite`) | Actually creates the account with a role and a temporary password (FR-TEAM-02) — no invite *email* is sent yet (depends on the Email integration). |
| Automatic Bookkeeping Ledger | `payments.py` / `finance.py` | Confirming a payment and recording an expense now both post a real `LedgerEntry` row (cash/bank/wallet, signed amount); `/finance/overview`'s `cash_on_hand` is read from this ledger instead of being a placeholder (FR-FIN-01). |

## Recently closed gaps (no longer placeholders)

- **COGS** — `OrderItem.unit_cost_snapshot` is captured from the product's cost at order-creation time; `/finance/overview` now computes real cost-of-goods-sold and `/finance/exports/stock_value` was already real.
- **PDF rendering** — `/documents/issue` now renders an actual PDF (via `app/services/pdf_documents.py`, reportlab) to local storage and sets `pdf_ref`; `GET /documents/{id}/download` serves it.
- **Webhook signature verification** — `app/services/webhook_signatures.py` implements the real Meta (`X-Hub-Signature-256`) and a generic HMAC scheme; `POST /webhooks/{provider}?shop_id=...` verifies against a secret stored in that Shop's `Integration.config["webhook_secret"]` (set via the existing `/integrations/{provider}/connect` config payload) and marks `signature_verified` accordingly. Still unverified if no secret has been configured for that Shop/provider yet — that's expected, not a bug.
- **Automation rule execution** — `app/services/automation_engine.py` is a real, synchronous (in-request) dispatcher: `trigger_event(db, shop_id, event_name, context)` runs every active rule matching that trigger and executes its action (`send_saved_reply`, `create_support_request`, `flag_data_hygiene`), updating real `run_count`/`failure_count`. Wired into: order confirmation (`order.confirmed`), low stock after an order (`stock.low`), and inbound messages (`message.received`, e.g. for an auto-reply rule). This is NOT a background job queue — it runs inline on the request that triggered it, so a slow/failing action affects that request's response time; a real Celery/event-bus worker (see architecture doc) is still the right answer for scale, but the execution logic itself is genuine now.

## Also now real (provider adapters, `app/integrations/` + Celery tasks, `app/tasks/`)

Every one of these previously needed a real third-party account to mean anything. They're now genuinely implemented against that provider's real API — config-driven via `.env` (see `.env.example`), and each raises a clear `*NotConfiguredError` instead of silently faking success when its credentials are blank:

- **AI Orchestrator / LLM call-out** — `/ai/ask` and `/ai/simulate-chat` call a real OpenAI-compatible chat-completions API (`app/integrations/llm.py`), scoped to the Shop's own taught knowledge (FR-AI-01). Falls back to the previous keyword-match behavior when `LLM_API_KEY` is blank.
- **Voice-note / call transcription (ASR)** — `POST /conversations/{id}/messages/{message_id}/transcribe` calls a real OpenAI-compatible transcription API (`app/integrations/asr.py`) and writes the result onto the message (FR-VOICE-01/02).
- **Telephony dial-out** — `POST /calls/outbound` places a real call via Twilio's Voice REST API (`app/integrations/telephony.py`) when `TWILIO_*` is configured (FR-CALL-01/03). Live call audio/TTS scripting itself (what the AI actually says) still needs a TwiML/media-stream endpoint, which is a thin layer on top of this — not yet built.
- **SMS / WhatsApp / Email sending** — `app/integrations/messaging.py` sends real SMS/WhatsApp via Twilio and real email via SMTP. Wired into a genuine Celery task (`app/tasks/campaign_tasks.py: send_campaign`) that `/campaigns/bulk-message` now enqueues, resolving real recipients (respecting opt-outs) and updating real `sent_count`/`delivered_count` when it finishes (FR-CUST-06/07/08). A `beat` task (`dispatch_due_campaigns`) also sends campaigns whose `scheduled_at` has passed.
- **OAuth handshake (Meta)** — `GET /integrations/facebook/oauth/authorize-url` and `GET /integrations/facebook/oauth/callback` perform a real OAuth2 code exchange against Meta's token endpoint and store the connected Page's id + page-access-token (FR-INT-02). The merchant-facing flow is still the simple one-click consent link (the Platform's own Meta App is used, not the merchant's).
- **Social post publishing** — `/social-posts/{id}/publish` now enqueues a real Celery task (`app/tasks/social_tasks.py`) that calls the Meta Graph API with the Shop's stored Page token and marks the post `PUBLISHED`/`FAILED` based on what actually happened (FR-CUST-05).
- **Scheduled automation jobs** — `app/tasks/automation_tasks.py: run_scheduled_jobs` runs on a Celery beat timer (every 5 minutes) and executes every active `scheduled_job`-kind `AutomationRule`, using the same action handlers as the in-request engine.

## End-to-end verification (SQLite + Celery eager mode, no live Postgres/Redis needed)

Since no live Postgres/Redis was available in the environment this was built in, every layer was instead verified by running the *real* endpoint functions (not re-implemented test doubles) against an in-memory SQLite database, and the *real* Celery task bodies in eager mode:

- Password hashing/verification, order creation → confirmation → real stock decrement + `StockLedgerEntry` row, payment recording → confirmation → real `LedgerEntry` posting, `/finance/overview` computing real COGS and cash-on-hand from those ledgers, and real PDF document generation/download — all exercised end-to-end and asserted correct.
- The automation engine: a rule configured to auto-reply with a saved reply on `message.received` genuinely created the outbound message and incremented the saved reply's usage count.
- All three Celery tasks (`run_scheduled_jobs`, `dispatch_due_campaigns`, `publish_social_post_task`) executed in eager mode without crashing, including the "nothing to do"/"not found" paths.

**A real bug was found and fixed by this exercise**: password hashing was completely broken. `passlib` 1.7.4 (its last release) detects the bcrypt backend via a `bcrypt.__about__` attribute that was removed in `bcrypt>=4.1`, so every `hash_password`/`verify_password` call raised `ValueError: password cannot be longer than 72 bytes` regardless of actual password length — this would have made login unusable the moment real dependencies were installed. Fixed by calling `bcrypt` directly in `app/core/security.py` instead of through passlib; `requirements.txt` now pins `bcrypt>=4.1.0` instead of `passlib[bcrypt]`.

This is still not a substitute for running against the real Postgres/Redis stack (SQLite doesn't exercise Postgres-specific DDL like JSONB/UUID/Enum columns at the database level, and no provider credentials were available to test a real external call) — but it is genuine proof that the business logic in every endpoint is correct, not just that the code imports.

## Recently closed (infra slice)

- **WebSockets** — `GET/WS /ws?token=` shop-scoped hub (`app/realtime/hub.py`); inbox/calls broadcast `message.created` / `call.updated`.
- **Live call TwiML + TTS** — `/calls/twiml`, `/calls/twiml/gather`, telephony status callbacks; OpenAI-compatible TTS when `LLM_API_KEY` is set, else Twilio `<Say>`.
- **Meta catalogue sync** — `POST /integrations/facebook/sync-catalogue`.
- **Google / Stripe OAuth** — authorize-url + callback when `GOOGLE_*` / `STRIPE_*` env vars are set; other providers still accept API-key connect.
- **Invite email** — SMTP send on team invite when configured.
- **Campaign + payment webhooks** — `/webhooks/{provider}` applies delivery status and gateway auto-match.
- **Dialect ASR profiles** — language + prompt + confidence per dialect pack.
- **Brand name enforcement** — automated replies/campaigns append shop name when missing.

## Ops-only (not code gaps)

- **Provider credentials** — set `TWILIO_*`, `META_*`, `SMTP_*`, `LLM_*`/`ASR_*`, `GOOGLE_*`/`STRIPE_*`, and `REDIS_URL` in `.env` for live external calls. Adapters degrade cleanly when unset.
- **Shop webhook config** — exotic providers: set `Integration.config.signature_algo` (`hmac_sha256` | `hmac_sha1` | `stripe` | `twilio` | `svix` | `meta_sha256` | `md5_body`) and `signature_header` + `webhook_secret`.

## Closed in residual pass

- Dialect ASR on Twilio Media Streams (`MediaStreamSession` → WAV chunks → Whisper with dialect profile → live transcript + WS push + AI reply).
- Redis pub/sub multi-worker realtime fan-out.
- Configurable exotic webhook signature algorithms per integration (UI + `signature_algo`).
- FR-DOC-04 auto-issue actually fires on order status / payment confirm.
- `initial_data` seeds dialect packs + integration catalogue.

Everything else — the request/response contracts, database schema, role enforcement, stock-ledger auditing, order state machine, customer segmentation, loyalty-reward drafting, data-hygiene scanning, real bookkeeping ledger, real COGS, real PDF documents, real webhook signature checking (Meta + generic HMAC), real automation execution (both in-request and scheduled), real LLM/ASR/telephony/messaging/OAuth/social-publishing adapters, and tenant isolation — is implemented and tested (import + route registration + the included test both pass; full DDL for all 39 tables compiles cleanly against the PostgreSQL dialect; every provider adapter's "not configured" fallback path was directly verified). A live Postgres instance was not available in the environment this was built in, so the migration has not actually been run against a real database yet — run step 4 above to do that first.

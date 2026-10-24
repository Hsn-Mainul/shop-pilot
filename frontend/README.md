# ShopPilot — Merchant Web Console

React + TypeScript admin console implementing the SRS module surface against the FastAPI backend.

## Stack

- Vite + React 19 + TypeScript
- React Router
- TanStack Query
- JWT auth (login form + refresh)
- EN/BN locale switch (nav + page titles)

## Setup

```bash
cd frontend
npm install
cp .env.example .env   # if needed
npm run dev
```

App: http://localhost:5175  
API (default): http://localhost:8001/api/v1

Demo login (after `python -m app.initial_data` in backend):

- Email: `owner@demo-shop.test`
- Password: `ChangeMe123!`

## Modules (SRS-aligned)

| Nav group | Screens |
|---|---|
| Home | Overview (KPIs, revenue/channels, fulfilment), AI Control Room (tasks, credit meter, toggles), Setup |
| Sell | Inbox (channel filter, saved replies, handover), Comments, Calls (monitor, persona, routing, dialects), Orders, Payments, Delivery (COD by courier), Saved Replies |
| Catalogue | Products (photo, bulk CSV), Services (pricing/schedule/recurrence), Inventory (ledger/serial/batch) |
| Customers | All / Segments / Blocked tabs, Reviews, Loyalty |
| Grow | Social Studio (AI caption/hashtags, product tag), AI Assistant, Train AI, Campaigns |
| Money | Finance (P&L, forecast, CSV exports), Documents (template gallery) |
| Automate | Recipe gallery, rules/workflows/jobs tabs |
| Shop | Team & shifts (AI draft), Integrations (guided connect), Plan, Data Hygiene, Settings, Support |

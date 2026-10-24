# Feature & Technology Analysis — AI Social-Commerce Shop Automation Platform

This document summarizes the feature inventory behind the SRS and the current technology-stack decision. It replaces the earlier analysis note and is written generically (no third-party product names).

---

## 1. Feature Inventory (Baseline Scope)

The baseline feature set targeted for parity with comparable products in this category:

### 1.1 Core Navigation / Modules
- **Overview**: Home dashboard (daily brief, "Needs Attention" KPI tiles: chats waiting, payment checks, orders to pack, failed deliveries, orders on hold, low stock, sold out), revenue chart, latest orders, order pipeline, best days, sales channels, fulfilment snapshot.
- **AI Control Room**: a central hub — daily task list, toggle switches per AI module (Conversations, Studio, Fulfilment, Money, Customers, Team, Guardian), AI credit meter, escalation feed for stuck automations.
- **Sell**: Unified inbox (requires channel connection), Comments (auto-hide spam/phone numbers, AI auto-reply toggle), Saved Replies (shortcut-tagged, merge-variable templates, bilingual), Orders (status pipeline New → Confirmed → Packed → Shipped → Delivered; spreadsheet sync), Payments (manual payment-matching queue, AI auto-confirm toggle, payment-proof capture), Delivery (courier booking & tracking pipeline, COD reconciliation).
- **Catalogue**: Products (photo+name+price minimum; bulk import; cloud-photo import), Services (separate type with pricing models — Fixed/From/On Quote; delivery location; scheduling — time-slot or due-date; recurrence), Inventory (stock by variant/serial/batch, low-stock & sold-out alerts, stock value).
- **Customers**: customer list with acquisition source, segmentation, loyalty/rewards automation, blocked list, reviews.
- **Grow**: Social content studio (AI caption/hashtag/best-time writer, shoppable tagging), conversational AI assistant over live shop data, AI training interface (facts/FAQs/policies/files, review-before-adopt).
- **Money**: Finance/books (P&L, cash forecast, ledgers), expense entry, statements, accountant-ready exports.
- **Automate**: Rules, Workflows, Scheduled jobs, Sending Rules, pre-built Recipes, run/time-saved/failure stats.
- **Shop (admin)**: Setup checklist, Team & Roles (RBAC: Super Admin/Admin/Sales/Support/Warehouse), shift planning, data-hygiene audit, Integrations hub, Invoice & Receipt template gallery with auto-issue rules, Plan & Usage, Settings, Support.

### 1.2 Integrations Catalogue
- **Messaging**: social Page/Messenger, Instagram Direct, WhatsApp Business, Telegram, custom webhook channel.
- **Payments**: multiple mobile-wallet and payment-link gateways.
- **Couriers**: multiple parcel/courier providers (booking, tracking, COD settlement).
- **Shop builders / marketplaces**: native storefront plus external storefront and marketplace connectors.
- **Productivity suite**: spreadsheet, drive/storage, calendar/meeting integrations.
- **Email**: own mailbox or managed transactional sender.
- **AI providers**: optional bring-your-own key, managed default requires none.
- **Developer tools**: outgoing webhooks, API keys (advanced tier).

### 1.3 Pricing Model Pattern (Reference)
A tiered plan structure (Free / Pro / Business / Enterprise) differentiated by connected channels/numbers, team seats, and monthly AI-credit allowance is the typical pattern for this product category.

---

## 2. Gap-Driven Requirements (Beyond Baseline)

These came from direct operational feedback and are treated as must-have differentiators, not optional extras:

1. **Business-type flexibility** — the system must not assume a single product category; category taxonomy must be open and configurable.
2. **Simplified channel connection** — connecting a messaging channel must not require manual developer-level credentials (app ID/secret, redirect URIs) as the default path.
3. **Catalogue auto-sync from a connected Page** — products already listed on a connected social catalogue should not need full manual re-entry.
4. **Brand name in every automated message** — all transactional templates must include the shop/brand name by default, non-removably.
5. **Voice-note understanding** — inbound customer voice messages must be transcribed and answerable, not ignored.
6. **Accurate, auditable stock counts** — real-time stock decrement/restore with a full adjustment log.
7. **Bulk outbound messaging** — bulk email, SMS, and WhatsApp campaigns to customer segments, not only one-to-one chat.
8. **Fast onboarding** — adding a product and connecting a channel must be achievable in minimal steps, matching or beating the simplest flows seen in this product category.
9. **Overall ease of use** — minimize technical jargon and manual data entry throughout.
10. **Live AI voice calling** — the AI assistant must be able to answer and place real phone calls, not just reply in chat.
11. **Regional dialect understanding** — speech recognition must cover Standard Bangla, English, and major regional Bangla varieties (e.g., Sylheti, Chittagonian, Noakhailla, Barisal, Mymensingh, Rangpuri), not only standard speech.

These map directly to the functional requirements in the SRS (see the SRS's traceability section for exact requirement IDs).

---

## 3. Technology Stack Decision

After reviewing the trade-offs between a multi-language microservice split and a single-language backend, the project has standardized on the following stack:

| Layer | Decision | Rationale |
|---|---|---|
| Frontend (web admin console) | **React + TypeScript** | Best library ecosystem for dashboards/tables/forms; pairs naturally with a Python backend; large hiring pool. |
| Frontend (future native mobile) | **React Native** | Reuses business logic and a large share of UI components from the web app. |
| Backend — API gateway & business services | **Python (FastAPI)**, modular monolith | One language across the whole backend avoids a network hop between business logic and AI; FastAPI gives async performance suitable for chat/call-heavy I/O workloads. |
| Backend — AI Orchestrator & NLU | **Python** | Same process/language as the rest of the backend; direct access to the near-complete Python ML/LLM ecosystem. |
| Backend — ASR / TTS / Voice Engine | **Python** | No serialization boundary with NLU/Orchestrator; pluggable regional-dialect acoustic models. |
| Background jobs / automation engine | **Celery (Python)** | Standard, mature choice for scheduled jobs and async processing in a Python stack. |
| Primary database | **PostgreSQL** (+ pgvector) | Tenant-partitioned relational store; pgvector covers the AI-knowledge vector-store need without a separate database. |
| Cache / sessions / event bus | **Redis** | Low-latency cache, Celery broker, and lightweight event-stream backbone in one component. |
| Infrastructure | **Docker + Kubernetes**, infrastructure-as-code | Consistent deployment across environments for every Python service and the React app. |

**Why not multi-language microservices:** the team evaluated splitting AI/Voice into a separate Python service alongside a .NET or Node.js core, but decided the added latency, versioning overhead, and operational complexity were not justified given the close coupling between conversation NLU and voice handling. A single Python backend, organized as a modular monolith (clear internal module boundaries, not a tangle), keeps the option open to peel out a true microservice later (e.g., the Voice Engine) if load eventually requires independent scaling.

This decision is now reflected in the System Architecture & Development Flow document's technology-stack section and should be treated as the default for all new service work unless a specific component's scale requirements force a reassessment.

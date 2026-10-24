# Meta (Facebook & Instagram) Multi-Tenant SaaS Integration Guide

This guide documents the complete configuration, architecture, and step-by-step setup for connecting Facebook Pages and Instagram accounts in the ShopPilot multi-tenant SaaS chatbot platform.

---

## 1. Quick Reference & Direct Links

* **App Name:** `shop-pilot`
* **Meta App ID:** `1853795219138794`
* **Direct Meta Dashboard Links:**
  * **App Dashboard:** [https://developers.facebook.com/apps/1853795219138794/dashboard/](https://developers.facebook.com/apps/1853795219138794/dashboard/)
  * **Basic Settings:** [https://developers.facebook.com/apps/1853795219138794/settings/basic/](https://developers.facebook.com/apps/1853795219138794/settings/basic/)
  * **Webhooks Configuration:** [https://developers.facebook.com/apps/1853795219138794/webhooks/](https://developers.facebook.com/apps/1853795219138794/webhooks/)
  * **Use Cases (Messenger & Instagram):** [https://developers.facebook.com/apps/1853795219138794/use_cases/](https://developers.facebook.com/apps/1853795219138794/use_cases/)
  * **Go Live Checklist:** [https://developers.facebook.com/apps/1853795219138794/go_live/](https://developers.facebook.com/apps/1853795219138794/go_live/)

---

## 2. Architecture: Multi-Tenant Platform Model

```
                    ┌────────────────────────────┐
                    │      ShopPilot Platform    │
                    │      (One Meta App ID)     │
                    └─────────────┬──────────────┘
                                  │
       ┌──────────────────────────┴──────────────────────────┐
       ▼                                                     ▼
┌──────────────┐                                      ┌──────────────┐
│   Client A   │                                      │   Client B   │
│ (Shop ID: 1) │                                      │ (Shop ID: 2) │
└──────┬───────┘                                      └──────┬───────┘
       │                                                     │
       ▼                                                     ▼
┌──────────────────────────────┐              ┌──────────────────────────────┐
│ Facebook Pages:              │              │ Facebook Pages:              │
│ - BallotBuzz                 │              │ - Organic Foods BD           │
│ - UrbanTwist                 │              │ - Trendy Shoes               │
│ Instagram:                   │              │ Instagram:                   │
│ - @ballotbuzz_official       │              │ - @organic_bd                │
└──────────────────────────────┘              └──────────────────────────────┘
```

### Key Principles:
1. **Zero Client Effort:** Clients never need a Meta developer account or API keys. They click **Connect Facebook Page**, approve on Meta's official consent screen, and their pages appear automatically in their dashboard.
2. **Complete Isolation:** Each merchant is assigned an isolated `shop_id`. Tokens, pages, Instagram accounts, products, and customer conversations are segmented by `shop_id`.
3. **Webhook Routing:** When a customer sends a message to any connected Facebook Page, Meta's webhook sends the Page ID. The backend maps the Page ID to the merchant's `shop_id` and dispatches the AI reply using only that merchant's catalog and policies.

---

## 3. Environment Configuration (`backend/.env`)

Add or update these keys in your `backend/.env` file:

```env
# Public domain where your backend is accessible to Meta (Ngrok during development or production domain)
PUBLIC_BASE_URL=https://cleaver-construct-percolate.ngrok-free.dev

# Meta App Credentials
META_APP_ID=1853795219138794
META_APP_SECRET=56175c66170ace93ac78cc14e47f933b

# Meta OAuth Redirect URI (Matches Valid OAuth Redirect URIs in Meta Dashboard)
META_OAUTH_REDIRECT_URI=https://cleaver-construct-percolate.ngrok-free.dev/api/v1/integrations/facebook/oauth/callback

# Webhook Verify Token (Entered into Meta Webhook setup)
META_WEBHOOK_VERIFY_TOKEN=shoppilot-dev-verify
```

> **Note on Changing Ngrok URLs:** If your ngrok session restarts and gives you a new domain (e.g. `xyz.ngrok-free.app`), update `PUBLIC_BASE_URL` and `META_OAUTH_REDIRECT_URI` in `.env`, and update the **App domains**, **Site URL**, and **Valid OAuth Redirect URIs** in the Meta dashboard.

---

## 4. Meta Developer Dashboard Setup

### A. Basic Settings
* **Location:** **App settings** &rarr; **Basic**
* **App Domains:** Enter your domain without protocol:
  ```text
  cleaver-construct-percolate.ngrok-free.dev
  ```
* **Privacy Policy URL:** Enter a valid URL:
  ```text
  https://cleaver-construct-percolate.ngrok-free.dev/privacy
  ```
* **Category:** Select `Business and Pages`.
* **Platform:** Click **+ Add Platform** at the bottom &rarr; Choose **Website** &rarr; Set **Site URL**:
  ```text
  https://cleaver-construct-percolate.ngrok-free.dev/
  ```
* **Click Save changes.**

---

### B. Facebook Login for Business Settings
* **Location:** **Facebook Login for Business** &rarr; **Settings**
* **Client OAuth Login:** `Yes`
* **Web OAuth Login:** `Yes`
* **Valid OAuth Redirect URIs:**
  ```text
  https://cleaver-construct-percolate.ngrok-free.dev/api/v1/integrations/facebook/oauth/callback
  ```
* **Click Save changes.**

---

### C. Webhooks Setup
* **Location:** [https://developers.facebook.com/apps/1853795219138794/webhooks/](https://developers.facebook.com/apps/1853795219138794/webhooks/)
* Select **`Page`** from the object dropdown.
* Click **Edit Subscription** (or **Subscribe to this object**):
  * **Callback URL:**
    ```text
    https://cleaver-construct-percolate.ngrok-free.dev/api/v1/webhooks/meta
    ```
  * **Verify Token:**
    ```text
    shoppilot-dev-verify
    ```
  * Click **Verify and Save**.
* In the subscription fields table, click **Subscribe** next to:
  * `messages` (Inbound customer direct messages)
  * `messaging_postbacks` (Button clicks and quick replies)

---

## 5. OAuth Scopes & Permissions

The OAuth authorization URL is built in `backend/app/integrations/meta_graph.py`:

```python
params = {
    "client_id": settings.meta_app_id,
    "redirect_uri": settings.meta_oauth_redirect_uri,
    "state": state,
    "scope": "pages_show_list,pages_messaging,instagram_basic,business_management",
}
```

### Purpose of Each Scope:
| Scope | Description |
|---|---|
| `pages_show_list` | Fetches the merchant's list of managed Facebook Pages from `/me/accounts`. |
| `pages_messaging` | Allows the chatbot to receive customer messages and send automated replies. |
| `instagram_basic` | Discovers linked Instagram Business Accounts and usernames. |
| `business_management` | Enables Business Portfolio association for enterprise shops. |

---

## 6. Automatic Webhook Subscription on Connect

When a merchant completes OAuth, the backend callback automatically runs:

```python
# Automatically subscribes the Page to the app's webhooks
for p in pages:
    pid = p.get("id")
    ptoken = p.get("access_token")
    if pid and ptoken:
        subscribe_page_to_app(pid, ptoken)
```

This calls `POST /{page_id}/subscribed_apps?subscribed_fields=messages,messaging_postbacks` using the Page Access Token. You do **not** need to manually subscribe individual pages in the Meta dashboard—connecting the page in ShopPilot handles it automatically.

---

## 7. Going Live for Public Clients (Production)

While the app is in **Development Mode**, only developers and testers can connect. To allow any public business to connect:

1. **Complete Use Case Permissions:**
   * Go to **Use Cases** &rarr; **Engage with customers on Messenger from Meta**.
   * Under Permissions, request **Advanced Access** for:
     * `pages_show_list`
     * `pages_messaging`
2. **Submit for Meta App Review:**
   * Provide a short screen recording demonstrating:
     1. Merchant clicks **Connect Facebook Page**.
     2. Merchant selects their page and approves.
     3. Customer sends a message on Messenger.
     4. AI chatbot responds in the conversation.
3. **Switch to Live:**
   * Go to **Go Live** checklist &rarr; click **Go Live**.
   * The *"App not active"* screen will disappear for all external clients worldwide.

---

## 8. Common Troubleshooting

| Error | Cause | Solution |
|---|---|---|
| `503 Service Unavailable: Meta app credentials / redirect URI are not configured` | `META_APP_ID` or `META_APP_SECRET` missing in `backend/.env`. | Paste your App ID and Secret into `.env` and restart backend. |
| `App not active` | The app is in Development Mode and the logged-in user is not an Admin/Tester. | Log in with the app creator account, or add user under **App roles &rarr; Roles**, or switch app to **Live**. |
| `Can't load URL: The domain of this URL isn't included in the app's domains` | Ngrok domain not added to App Domains or Website Platform. | In Basic Settings, add domain to **App domains**, add **Website** platform with `Site URL`, and click **Save Changes**. |
| `Invalid Scopes` | Requesting unapproved scopes (e.g. `pages_manage_posts`). | Use only approved scopes: `pages_show_list,pages_messaging,instagram_basic,business_management`. |
| Chatbot does not receive messages | Webhook not subscribed to `messages` or page not subscribed. | Verify webhook callback URL in Meta and confirm `subscribed_apps` returned `{"success": true}`. |

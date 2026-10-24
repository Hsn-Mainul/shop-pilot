"""Registry of OUR OWN application pages/modules (not social media pages).

System Admin uses this to let the Product Owner mark any internal module
(Setup, Integrations, Products, ...) as visible to everyone or restricted to
specific team members. Keys mirror the frontend route paths (without the
leading slash) in app/App.tsx / AppShell.tsx.
"""

APP_PAGE_REGISTRY: list[tuple[str, str]] = [
    ("ai-control", "AI Control Room"),
    ("setup", "Setup"),
    ("inbox", "Inbox"),
    ("comments", "Comments"),
    ("calls", "Calls"),
    ("orders", "Orders"),
    ("payments", "Payments"),
    ("delivery", "Delivery"),
    ("saved-replies", "Saved Replies"),
    ("products", "Products"),
    ("services", "Services"),
    ("inventory", "Inventory"),
    ("customers", "Customers"),
    ("reviews", "Reviews"),
    ("loyalty", "Loyalty"),
    ("social", "Social Studio"),
    ("ai-assistant", "AI Assistant"),
    ("ai-training", "AI Training"),
    ("campaigns", "Campaigns"),
    ("finance", "Finance"),
    ("documents", "Documents"),
    ("automations", "Automations"),
    ("team", "Team"),
    ("integrations", "Integrations"),
    ("plan", "Plan"),
    ("data-hygiene", "Data Hygiene"),
    ("settings", "Settings"),
    ("support", "Support"),
]

APP_PAGE_LABELS: dict[str, str] = dict(APP_PAGE_REGISTRY)

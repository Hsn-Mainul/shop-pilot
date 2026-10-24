"""Pure detection logic for the Data Hygiene audit (FR-TEAM-05).

These functions only build in-memory DataHygieneIssue rows from already-loaded
customers/products; the caller is responsible for de-duplicating against
existing unresolved issues and committing to the database.
"""
import re
import uuid

from app.models.customer import Customer
from app.models.product import Product
from app.models.team_ops import DataHygieneIssue, DataHygieneIssueType

# Bangladeshi mobile numbers in the canonical form: +8801XXXXXXXXX
STANDARD_PHONE_RE = re.compile(r"^\+8801[0-9]{9}$")


def find_duplicate_customers(shop_id: uuid.UUID, customers: list[Customer]) -> list[DataHygieneIssue]:
    seen: dict[str, Customer] = {}
    issues: list[DataHygieneIssue] = []
    for customer in customers:
        key = (customer.phone or "").strip()
        if not key:
            continue
        if key in seen:
            issues.append(
                DataHygieneIssue(
                    shop_id=shop_id,
                    issue_type=DataHygieneIssueType.DUPLICATE_CUSTOMER,
                    related_id=customer.id,
                )
            )
        else:
            seen[key] = customer
    return issues


def find_non_standard_phones(shop_id: uuid.UUID, customers: list[Customer]) -> list[DataHygieneIssue]:
    issues: list[DataHygieneIssue] = []
    for customer in customers:
        if customer.phone and not STANDARD_PHONE_RE.match(customer.phone):
            issues.append(
                DataHygieneIssue(
                    shop_id=shop_id,
                    issue_type=DataHygieneIssueType.NON_STANDARD_PHONE,
                    related_id=customer.id,
                )
            )
    return issues


def find_products_missing_fields(shop_id: uuid.UUID, products: list[Product]) -> list[DataHygieneIssue]:
    issues: list[DataHygieneIssue] = []
    for product in products:
        if product.price is None:
            issues.append(
                DataHygieneIssue(
                    shop_id=shop_id,
                    issue_type=DataHygieneIssueType.MISSING_PRICE,
                    related_id=product.id,
                )
            )
        if not product.photo_url:
            issues.append(
                DataHygieneIssue(
                    shop_id=shop_id,
                    issue_type=DataHygieneIssueType.MISSING_PHOTO,
                    related_id=product.id,
                )
            )
    return issues

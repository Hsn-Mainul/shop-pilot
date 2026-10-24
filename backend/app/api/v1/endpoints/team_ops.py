import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.models.product import Product
from app.services.data_hygiene import (
    find_duplicate_customers,
    find_non_standard_phones,
    find_products_missing_fields,
)
from app.models.team_member import TeamMember, TeamRole
from app.models.team_ops import DataHygieneIssue, LeaveRequest, LeaveStatus, Shift
from app.schemas.team_ops import (
    DataHygieneIssueOut,
    LeaveRequestCreate,
    LeaveRequestOut,
    LeaveStatusUpdate,
    ShiftConfirmRequest,
    ShiftOut,
)

router = APIRouter(tags=["team-ops"])


@router.get("/shifts", response_model=list[ShiftOut])
def list_shifts(
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShiftOut]:
    return db.query(Shift).filter(Shift.shop_id == current_user.shop_id).order_by(Shift.shift_date).all()


def _hours_by_weekday_from_orders(db: Session, shop_id, lookback_days: int = 28) -> dict[int, float]:
    """Average order count per weekday → planned hours (FR-TEAM-04 volume signal)."""
    from datetime import datetime, timezone

    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    orders = (
        db.query(Order)
        .filter(Order.shop_id == shop_id, Order.created_at >= since)
        .all()
    )
    counts = {i: 0 for i in range(7)}
    for o in orders:
        if o.created_at:
            counts[o.created_at.weekday()] += 1
    weeks = max(1, lookback_days / 7)
    hours: dict[int, float] = {}
    for wd, count in counts.items():
        avg = count / weeks
        # Map daily order volume → staffing hours
        if avg <= 2:
            hours[wd] = 4
        elif avg <= 8:
            hours[wd] = 6
        elif avg <= 20:
            hours[wd] = 8
        else:
            hours[wd] = 10
    return hours


def _llm_adjust_hours(shop_name: str, members: list[TeamMember], hours_by_wd: dict[int, float]) -> dict[int, float]:
    """Optional LLM nudge for staffing intensity; falls back to volume map."""
    from app.integrations.llm import LLMNotConfiguredError, chat_completion

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    summary = ", ".join(f"{day_names[i]}={hours_by_wd.get(i, 0):.0f}h" for i in range(7))
    prompt = (
        f"Shop '{shop_name}' has {len(members)} staff. Suggested daily hours from order volume: {summary}. "
        "Reply with ONLY seven comma-separated integers for Mon-Sun planned hours (4-12 each). No prose."
    )
    try:
        reply = chat_completion(
            "You are a workforce planner. Output only numbers.",
            prompt,
            max_tokens=40,
        )
        nums = [int(x.strip()) for x in reply.replace("\n", ",").split(",") if x.strip().lstrip("-").isdigit()]
        if len(nums) >= 7:
            return {i: max(4, min(12, nums[i])) for i in range(7)}
    except (LLMNotConfiguredError, Exception):
        pass
    return hours_by_wd


@router.post("/shifts/draft", response_model=list[ShiftOut], status_code=status.HTTP_201_CREATED)
def draft_shifts(
    days: int = 7,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[ShiftOut]:
    """FR-TEAM-04: AI/volume-drafted shifts from recent order patterns (+ LLM when configured)."""
    members = (
        db.query(TeamMember)
        .filter(TeamMember.shop_id == current_user.shop_id, TeamMember.is_active.is_(True))
        .all()
    )
    if not members:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active team members")

    hours_by_wd = _hours_by_weekday_from_orders(db, current_user.shop_id)
    hours_by_wd = _llm_adjust_hours(current_user.shop.name, members, hours_by_wd)

    # Rotate members so heavy days get more coverage when volume is high
    created: list[Shift] = []
    start = date.today()
    for offset in range(max(1, min(days, 14))):
        day = start + timedelta(days=offset)
        wd = day.weekday()
        planned = int(hours_by_wd.get(wd, 6))
        # Weekends: still draft if historical volume justifies it
        active_members = members
        if wd >= 5 and planned <= 4:
            continue
        if planned >= 10 and len(members) > 1:
            # Assign everyone on peak days
            active_members = members
        elif len(members) > 1:
            # Rotate: pick half the team (at least 1) based on day index
            n = max(1, (len(members) + 1) // 2)
            start_idx = offset % len(members)
            active_members = [members[(start_idx + i) % len(members)] for i in range(n)]

        for member in active_members:
            exists = (
                db.query(Shift)
                .filter(
                    Shift.shop_id == current_user.shop_id,
                    Shift.team_member_id == member.id,
                    Shift.shift_date == day,
                )
                .first()
            )
            if exists:
                continue
            shift = Shift(
                shop_id=current_user.shop_id,
                team_member_id=member.id,
                shift_date=day,
                planned_hours=planned,
                is_confirmed=False,
            )
            db.add(shift)
            created.append(shift)
    db.commit()
    for s in created:
        db.refresh(s)
    return created


@router.patch("/shifts/{shift_id}", response_model=ShiftOut)
def confirm_shift(
    shift_id: uuid.UUID,
    payload: ShiftConfirmRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ShiftOut:
    shift = (
        db.query(Shift)
        .filter(Shift.id == shift_id, Shift.shop_id == current_user.shop_id)
        .first()
    )
    if shift is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    shift.is_confirmed = payload.is_confirmed
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@router.post("/leave-requests", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
def request_leave(
    payload: LeaveRequestCreate,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaveRequestOut:
    leave = LeaveRequest(team_member_id=current_user.id, **payload.model_dump())
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


@router.get("/leave-requests", response_model=list[LeaveRequestOut])
def list_leave_requests(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[LeaveRequestOut]:
    return (
        db.query(LeaveRequest)
        .join(TeamMember, LeaveRequest.team_member_id == TeamMember.id)
        .filter(TeamMember.shop_id == current_user.shop_id)
        .all()
    )


@router.patch("/leave-requests/{leave_id}", response_model=LeaveRequestOut)
def decide_leave_request(
    leave_id: uuid.UUID,
    payload: LeaveStatusUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> LeaveRequestOut:
    leave = (
        db.query(LeaveRequest)
        .join(TeamMember, LeaveRequest.team_member_id == TeamMember.id)
        .filter(LeaveRequest.id == leave_id, TeamMember.shop_id == current_user.shop_id)
        .first()
    )
    if leave is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    leave.status = payload.status
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


@router.get("/data-hygiene/issues", response_model=list[DataHygieneIssueOut])
def list_data_hygiene_issues(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[DataHygieneIssueOut]:
    return (
        db.query(DataHygieneIssue)
        .filter(DataHygieneIssue.shop_id == current_user.shop_id, DataHygieneIssue.is_resolved.is_(False))
        .all()
    )


@router.post("/data-hygiene/scan", response_model=list[DataHygieneIssueOut])
def run_data_hygiene_scan(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[DataHygieneIssueOut]:
    """Recompute data-hygiene findings for this shop (FR-TEAM-05)."""
    shop_id = current_user.shop_id
    customers = db.query(Customer).filter(Customer.shop_id == shop_id).all()
    products = db.query(Product).filter(Product.shop_id == shop_id).all()

    new_issues: list[DataHygieneIssue] = []
    new_issues += find_duplicate_customers(shop_id, customers)
    new_issues += find_non_standard_phones(shop_id, customers)
    new_issues += find_products_missing_fields(shop_id, products)

    for issue in new_issues:
        db.add(issue)
    db.commit()

    return (
        db.query(DataHygieneIssue)
        .filter(DataHygieneIssue.shop_id == shop_id, DataHygieneIssue.is_resolved.is_(False))
        .all()
    )


@router.patch("/data-hygiene/issues/{issue_id}/resolve", response_model=DataHygieneIssueOut)
def resolve_data_hygiene_issue(
    issue_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> DataHygieneIssueOut:
    issue = (
        db.query(DataHygieneIssue)
        .filter(DataHygieneIssue.id == issue_id, DataHygieneIssue.shop_id == current_user.shop_id)
        .first()
    )
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    issue.is_resolved = True
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.conversation import (
    ConversationChannel,
    ConversationStatus,
    Message,
    MessageDirection,
)
from app.models.customer import Customer
from app.models.loyalty import LoyaltyReward, RewardStatus
from app.models.team_member import TeamMember, TeamRole
from app.schemas.loyalty import LoyaltyRewardDecision, LoyaltyRewardOut
from app.services.channel_outbound import deliver_outbound
from app.services.inbox_ingest import get_or_create_conversation

router = APIRouter(prefix="/loyalty-rewards", tags=["loyalty"])


@router.get("", response_model=list[LoyaltyRewardOut])
def list_rewards(
    status_filter: RewardStatus = RewardStatus.WAITING,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> list[LoyaltyRewardOut]:
    return (
        db.query(LoyaltyReward)
        .filter(LoyaltyReward.shop_id == current_user.shop_id, LoyaltyReward.status == status_filter)
        .all()
    )


@router.patch("/{reward_id}/decide", response_model=LoyaltyRewardOut)
def decide_reward(
    reward_id: uuid.UUID,
    payload: LoyaltyRewardDecision,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> LoyaltyRewardOut:
    reward = (
        db.query(LoyaltyReward)
        .filter(LoyaltyReward.id == reward_id, LoyaltyReward.shop_id == current_user.shop_id)
        .first()
    )
    if reward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward draft not found")

    if not payload.approve:
        reward.status = RewardStatus.SET_ASIDE
        db.add(reward)
        db.commit()
        db.refresh(reward)
        return reward

    customer = db.get(Customer, reward.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    # Prefer an open messaging channel conversation; else start one on Facebook/WhatsApp
    channel = ConversationChannel.FACEBOOK
    if customer.phone and customer.phone.startswith("wa:"):
        channel = ConversationChannel.WHATSAPP
    elif customer.phone and customer.phone.startswith("ig:"):
        channel = ConversationChannel.INSTAGRAM
    elif customer.source == "whatsapp":
        channel = ConversationChannel.WHATSAPP

    conversation = get_or_create_conversation(db, current_user.shop_id, customer, channel)
    message = Message(
        conversation_id=conversation.id,
        direction=MessageDirection.OUTBOUND,
        text=reward.draft_message,
        sent_by_ai=True,
    )
    db.add(message)
    deliver_outbound(db, conversation, reward.draft_message, message=message)
    conversation.status = ConversationStatus.WAITING_ON_CUSTOMER
    db.add(conversation)

    reward.status = RewardStatus.SENT
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return reward

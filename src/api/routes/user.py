"""User management and tier API routes."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.users import User, UserTier, UsageRecord, TierLimit
from src.api.routes.auth import get_current_user

router = APIRouter()


# Pydantic schemas
class TierFeatures(BaseModel):
    """Features available in a tier."""

    alerts: bool
    backtesting: bool
    websocket: bool
    sdk: bool
    custom_factors: bool


class TierInfoResponse(BaseModel):
    """Information about a subscription tier."""

    tier: UserTier
    name: str
    requests_per_day: int
    requests_per_minute: int
    history_days: int
    features: TierFeatures
    monthly_price_usd: Decimal

    class Config:
        from_attributes = True


class TierComparisonResponse(BaseModel):
    """Response comparing all available tiers."""

    tiers: list[TierInfoResponse]
    current_tier: UserTier


class UsageDetailResponse(BaseModel):
    """Detailed usage statistics response."""

    requests_today: int
    requests_limit: int
    requests_percentage: float
    data_bytes_today: int
    websocket_connections_today: int
    alerts_triggered_today: int
    backtests_run_today: int
    tier: UserTier
    features: dict
    warning_level: Optional[str] = None  # "80%" or "95%" or None
    historical_usage: list[dict] = []


class UpgradeRequest(BaseModel):
    """Request to upgrade tier."""

    target_tier: UserTier


class UpgradeResponse(BaseModel):
    """Response after tier upgrade."""

    success: bool
    previous_tier: UserTier
    new_tier: UserTier
    prorated_amount_usd: Optional[Decimal] = None
    message: str
    new_features: list[str]


class UsageHistoryResponse(BaseModel):
    """Historical usage data."""

    date: datetime
    api_requests: int
    data_bytes_downloaded: int
    websocket_connections: int
    alerts_triggered: int
    backtests_run: int


# Helper functions
def get_tier_display_name(tier: UserTier) -> str:
    """Get display name for tier."""
    names = {
        UserTier.FREE: "Free",
        UserTier.PRO: "Professional",
        UserTier.ENTERPRISE: "Enterprise",
        UserTier.CUSTOM: "Custom",
    }
    return names.get(tier, tier.value.title())


def calculate_prorated_amount(
    current_tier_price: Decimal,
    new_tier_price: Decimal,
    days_remaining: int,
) -> Decimal:
    """Calculate prorated upgrade amount."""
    if days_remaining <= 0:
        return new_tier_price

    daily_difference = (new_tier_price - current_tier_price) / Decimal("30")
    return max(Decimal("0"), daily_difference * days_remaining)


# Routes
@router.get("/usage", response_model=UsageDetailResponse)
async def get_detailed_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed usage statistics for current user."""
    # Get today's usage
    today = datetime.utcnow().date()
    usage_query = (
        select(UsageRecord)
        .where(UsageRecord.user_id == current_user.id)
        .where(UsageRecord.date >= datetime.combine(today, datetime.min.time()))
    )

    usage_result = await db.execute(usage_query)
    usage_records = usage_result.scalars().all()

    requests_today = sum(r.api_requests for r in usage_records)
    data_bytes_today = sum(r.data_bytes_downloaded for r in usage_records)
    websocket_today = sum(r.websocket_connections for r in usage_records)
    alerts_today = sum(r.alerts_triggered for r in usage_records)
    backtests_today = sum(r.backtests_run for r in usage_records)

    # Get tier limits
    tier_query = select(TierLimit).where(TierLimit.tier == current_user.tier)
    tier_result = await db.execute(tier_query)
    tier_limit = tier_result.scalar_one_or_none()

    requests_limit = tier_limit.requests_per_day if tier_limit else 100
    requests_percentage = (requests_today / requests_limit * 100) if requests_limit > 0 else 0

    features = {}
    if tier_limit:
        features = {
            "alerts": tier_limit.alerts_allowed,
            "backtesting": tier_limit.backtesting_allowed,
            "websocket": tier_limit.websocket_allowed,
            "sdk": tier_limit.sdk_access,
            "custom_factors": tier_limit.custom_factors_allowed,
        }

    # Determine warning level
    warning_level = None
    if requests_percentage >= 95:
        warning_level = "95%"
    elif requests_percentage >= 80:
        warning_level = "80%"

    # Get historical usage (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    history_query = (
        select(UsageRecord)
        .where(UsageRecord.user_id == current_user.id)
        .where(UsageRecord.date >= thirty_days_ago)
        .order_by(UsageRecord.date.desc())
    )
    history_result = await db.execute(history_query)
    history_records = history_result.scalars().all()

    historical_usage = [
        {
            "date": r.date.isoformat(),
            "api_requests": r.api_requests,
            "data_bytes": r.data_bytes_downloaded,
        }
        for r in history_records
    ]

    return UsageDetailResponse(
        requests_today=requests_today,
        requests_limit=requests_limit,
        requests_percentage=requests_percentage,
        data_bytes_today=data_bytes_today,
        websocket_connections_today=websocket_today,
        alerts_triggered_today=alerts_today,
        backtests_run_today=backtests_today,
        tier=current_user.tier,
        features=features,
        warning_level=warning_level,
        historical_usage=historical_usage,
    )


@router.get("/tiers", response_model=TierComparisonResponse)
async def get_tier_comparison(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all available tiers for comparison."""
    tier_query = select(TierLimit).order_by(TierLimit.monthly_price_usd)
    tier_result = await db.execute(tier_query)
    tier_limits = tier_result.scalars().all()

    tiers = []
    for tl in tier_limits:
        tiers.append(
            TierInfoResponse(
                tier=tl.tier,
                name=get_tier_display_name(tl.tier),
                requests_per_day=tl.requests_per_day,
                requests_per_minute=tl.requests_per_minute,
                history_days=tl.history_days,
                features=TierFeatures(
                    alerts=tl.alerts_allowed,
                    backtesting=tl.backtesting_allowed,
                    websocket=tl.websocket_allowed,
                    sdk=tl.sdk_access,
                    custom_factors=tl.custom_factors_allowed,
                ),
                monthly_price_usd=tl.monthly_price_usd,
            )
        )

    return TierComparisonResponse(
        tiers=tiers,
        current_tier=current_user.tier,
    )


@router.post("/upgrade", response_model=UpgradeResponse)
async def upgrade_tier(
    upgrade_request: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upgrade user's subscription tier."""
    target_tier = upgrade_request.target_tier

    # Check if already on this tier
    if current_user.tier == target_tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Already on {target_tier.value} tier",
        )

    # Get tier order for upgrade validation
    tier_order = [UserTier.FREE, UserTier.PRO, UserTier.ENTERPRISE]
    try:
        current_idx = tier_order.index(current_user.tier)
        target_idx = tier_order.index(target_tier)
    except ValueError:
        # Custom tier - allow any upgrade
        current_idx = -1
        target_idx = len(tier_order)

    if target_idx <= current_idx:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot downgrade tier through this endpoint",
        )

    # Get tier pricing
    current_tier_query = select(TierLimit).where(TierLimit.tier == current_user.tier)
    target_tier_query = select(TierLimit).where(TierLimit.tier == target_tier)

    current_result = await db.execute(current_tier_query)
    target_result = await db.execute(target_tier_query)

    current_tier_limit = current_result.scalar_one_or_none()
    target_tier_limit = target_result.scalar_one_or_none()

    if not target_tier_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {target_tier.value}",
        )

    # Calculate prorated amount
    current_price = current_tier_limit.monthly_price_usd if current_tier_limit else Decimal("0")
    target_price = target_tier_limit.monthly_price_usd

    # Assume billing cycle resets on the 1st of each month
    today = datetime.utcnow()
    days_in_month = 30
    days_remaining = days_in_month - today.day

    prorated_amount = calculate_prorated_amount(current_price, target_price, days_remaining)

    # Update user tier
    previous_tier = current_user.tier
    current_user.tier = target_tier
    current_user.tier_upgraded_at = datetime.utcnow()

    await db.commit()
    await db.refresh(current_user)

    # Determine new features
    new_features = []
    if target_tier_limit.alerts_allowed and (not current_tier_limit or not current_tier_limit.alerts_allowed):
        new_features.append("Alert notifications")
    if target_tier_limit.backtesting_allowed and (not current_tier_limit or not current_tier_limit.backtesting_allowed):
        new_features.append("Backtesting")
    if target_tier_limit.websocket_allowed and (not current_tier_limit or not current_tier_limit.websocket_allowed):
        new_features.append("Real-time WebSocket streaming")
    if target_tier_limit.sdk_access and (not current_tier_limit or not current_tier_limit.sdk_access):
        new_features.append("SDK access")
    if target_tier_limit.custom_factors_allowed and (not current_tier_limit or not current_tier_limit.custom_factors_allowed):
        new_features.append("Custom factor creation")

    return UpgradeResponse(
        success=True,
        previous_tier=previous_tier,
        new_tier=target_tier,
        prorated_amount_usd=prorated_amount,
        message=f"Successfully upgraded from {previous_tier.value} to {target_tier.value}",
        new_features=new_features,
    )


@router.get("/usage/history", response_model=list[UsageHistoryResponse])
async def get_usage_history(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get historical usage data."""
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days must be between 1 and 365",
        )

    start_date = datetime.utcnow() - timedelta(days=days)

    query = (
        select(UsageRecord)
        .where(UsageRecord.user_id == current_user.id)
        .where(UsageRecord.date >= start_date)
        .order_by(UsageRecord.date.desc())
    )

    result = await db.execute(query)
    records = result.scalars().all()

    return [
        UsageHistoryResponse(
            date=r.date,
            api_requests=r.api_requests,
            data_bytes_downloaded=r.data_bytes_downloaded,
            websocket_connections=r.websocket_connections,
            alerts_triggered=r.alerts_triggered,
            backtests_run=r.backtests_run,
        )
        for r in records
    ]

"""Alert API routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.alerts import Alert, AlertHistory, AlertType, AlertDirection, NotificationChannel

router = APIRouter()


# Pydantic schemas
class AlertCreate(BaseModel):
    """Schema for creating an alert."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    alert_type: AlertType
    factor_id: Optional[int] = None
    ticker_list: list[str] = Field(default_factory=list)

    # Threshold config
    threshold_value: Optional[float] = None
    direction: Optional[AlertDirection] = None

    # Anomaly config
    sensitivity_std_devs: Optional[float] = Field(None, ge=1, le=5)
    baseline_period_days: Optional[int] = Field(None, ge=7, le=90)
    use_ml_detection: bool = False

    # Event config
    event_type: Optional[str] = None
    event_criteria: Optional[dict] = None
    geographic_filter: Optional[dict] = None

    # Notification
    notification_channel: NotificationChannel = NotificationChannel.EMAIL
    webhook_url: Optional[str] = None

    # Fatigue management
    cooldown_minutes: int = Field(default=0, ge=0)
    use_daily_digest: bool = False


class AlertUpdate(BaseModel):
    """Schema for updating an alert."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    threshold_value: Optional[float] = None
    direction: Optional[AlertDirection] = None
    notification_channel: Optional[NotificationChannel] = None
    webhook_url: Optional[str] = None
    cooldown_minutes: Optional[int] = Field(None, ge=0)


class AlertResponse(BaseModel):
    """Response schema for alert."""

    id: int
    name: str
    description: Optional[str]
    alert_type: AlertType
    factor_id: Optional[int]
    ticker_list: list[str]
    threshold_value: Optional[float]
    direction: Optional[AlertDirection]
    notification_channel: NotificationChannel
    is_enabled: bool
    trigger_count: int
    last_triggered_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertHistoryResponse(BaseModel):
    """Response schema for alert history."""

    id: int
    alert_id: int
    triggered_at: datetime
    trigger_value: Optional[float]
    trigger_context: dict
    notification_sent: bool
    is_read: bool

    class Config:
        from_attributes = True


# Routes
@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    alert_type: Optional[AlertType] = None,
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_db),
    # TODO: Add user dependency
):
    """List user's alerts."""
    query = select(Alert)  # TODO: Filter by user_id

    if alert_type:
        query = query.where(Alert.alert_type == alert_type)
    if enabled_only:
        query = query.where(Alert.is_enabled == True)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert: AlertCreate,
    db: AsyncSession = Depends(get_db),
    # TODO: Add user dependency
):
    """Create a new alert."""
    # Validate based on alert type
    if alert.alert_type == AlertType.THRESHOLD:
        if alert.threshold_value is None or alert.direction is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Threshold alerts require threshold_value and direction",
            )

    if alert.alert_type == AlertType.EVENT:
        if alert.event_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event alerts require event_type",
            )

    if alert.notification_channel == NotificationChannel.WEBHOOK:
        if not alert.webhook_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook alerts require webhook_url",
            )

    new_alert = Alert(
        user_id=1,  # TODO: Get from auth
        name=alert.name,
        description=alert.description,
        alert_type=alert.alert_type,
        factor_id=alert.factor_id,
        ticker_list=alert.ticker_list,
        threshold_value=alert.threshold_value,
        direction=alert.direction,
        sensitivity_std_devs=alert.sensitivity_std_devs,
        baseline_period_days=alert.baseline_period_days,
        use_ml_detection=alert.use_ml_detection,
        event_type=alert.event_type,
        event_criteria=alert.event_criteria,
        geographic_filter=alert.geographic_filter,
        notification_channel=alert.notification_channel,
        webhook_url=alert.webhook_url,
        cooldown_minutes=alert.cooldown_minutes,
        use_daily_digest=alert.use_daily_digest,
    )

    db.add(new_alert)
    await db.commit()
    await db.refresh(new_alert)

    return AlertResponse.model_validate(new_alert)


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific alert."""
    query = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    return AlertResponse.model_validate(alert)


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    update: AlertUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an alert."""
    query = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(alert, field, value)

    await db.commit()
    await db.refresh(alert)

    return AlertResponse.model_validate(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete an alert."""
    query = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    await db.delete(alert)
    await db.commit()


@router.post("/{alert_id}/test")
async def test_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Send a test notification for an alert."""
    query = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    # TODO: Send test notification
    return {
        "status": "test_sent",
        "alert_id": alert_id,
        "channel": alert.notification_channel.value,
    }


@router.get("/{alert_id}/history", response_model=list[AlertHistoryResponse])
async def get_alert_history(
    alert_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get trigger history for an alert."""
    query = (
        select(AlertHistory)
        .where(AlertHistory.alert_id == alert_id)
        .order_by(AlertHistory.triggered_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    history = result.scalars().all()

    return [AlertHistoryResponse.model_validate(h) for h in history]

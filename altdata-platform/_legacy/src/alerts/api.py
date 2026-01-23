"""API endpoints for alert management."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.database import get_db
from .models import AlertRule, AlertNotification, AlertCondition, NotificationChannel, NotificationStatus
from .engine import AlertEngine

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


# Request/Response Models

class AlertRuleCreate(BaseModel):
    """Request model for creating an alert rule."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    factor_name: str = Field(..., min_length=1, max_length=100)
    entity_id: Optional[str] = Field(None, max_length=50)
    condition: AlertCondition
    threshold: float
    lookback_days: int = Field(30, ge=1, le=365)
    notification_channel: NotificationChannel = NotificationChannel.SLACK
    notification_config: Optional[str] = None
    cooldown_minutes: int = Field(60, ge=1, le=1440)


class AlertRuleUpdate(BaseModel):
    """Request model for updating an alert rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    factor_name: Optional[str] = Field(None, min_length=1, max_length=100)
    entity_id: Optional[str] = Field(None, max_length=50)
    condition: Optional[AlertCondition] = None
    threshold: Optional[float] = None
    lookback_days: Optional[int] = Field(None, ge=1, le=365)
    is_active: Optional[bool] = None
    notification_channel: Optional[NotificationChannel] = None
    notification_config: Optional[str] = None
    cooldown_minutes: Optional[int] = Field(None, ge=1, le=1440)


class AlertRuleResponse(BaseModel):
    """Response model for alert rule."""
    id: int
    name: str
    description: Optional[str]
    factor_name: str
    entity_id: Optional[str]
    condition: AlertCondition
    threshold: float
    lookback_days: int
    is_active: bool
    notification_channel: NotificationChannel
    notification_config: Optional[str]
    cooldown_minutes: int
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertNotificationResponse(BaseModel):
    """Response model for alert notification."""
    id: int
    rule_id: int
    entity_id: Optional[str]
    factor_value: Optional[float]
    threshold: Optional[float]
    computed_value: Optional[float]
    triggered_at: datetime
    notified_at: Optional[datetime]
    notification_channel: Optional[NotificationChannel]
    notification_status: NotificationStatus
    error_message: Optional[str]

    class Config:
        from_attributes = True


class AlertRuleListResponse(BaseModel):
    """Response model for list of alert rules."""
    rules: List[AlertRuleResponse]
    total: int


class AlertNotificationListResponse(BaseModel):
    """Response model for list of notifications."""
    notifications: List[AlertNotificationResponse]
    total: int


# Endpoints

@router.post("/rules", response_model=AlertRuleResponse, status_code=201)
def create_rule(rule: AlertRuleCreate, db: Session = Depends(get_db)):
    """Create a new alert rule."""
    db_rule = AlertRule(
        name=rule.name,
        description=rule.description,
        factor_name=rule.factor_name,
        entity_id=rule.entity_id,
        condition=rule.condition,
        threshold=rule.threshold,
        lookback_days=rule.lookback_days,
        notification_channel=rule.notification_channel,
        notification_config=rule.notification_config,
        cooldown_minutes=rule.cooldown_minutes,
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule


@router.get("/rules", response_model=AlertRuleListResponse)
def list_rules(
    is_active: Optional[bool] = Query(None),
    factor_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List all alert rules."""
    query = db.query(AlertRule)

    if is_active is not None:
        query = query.filter(AlertRule.is_active == is_active)

    if factor_name:
        query = query.filter(AlertRule.factor_name == factor_name)

    rules = query.order_by(AlertRule.created_at.desc()).all()

    return AlertRuleListResponse(rules=rules, total=len(rules))


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    """Get a specific alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
def update_rule(rule_id: int, update: AlertRuleUpdate, db: Session = Depends(get_db)):
    """Update an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    db.delete(rule)
    db.commit()


@router.get("/notifications", response_model=AlertNotificationListResponse)
def list_notifications(
    rule_id: Optional[int] = Query(None),
    entity_id: Optional[str] = Query(None),
    status: Optional[NotificationStatus] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List alert notifications."""
    query = db.query(AlertNotification)

    if rule_id:
        query = query.filter(AlertNotification.rule_id == rule_id)

    if entity_id:
        query = query.filter(AlertNotification.entity_id == entity_id)

    if status:
        query = query.filter(AlertNotification.notification_status == status)

    if start_date:
        query = query.filter(AlertNotification.triggered_at >= start_date)

    if end_date:
        query = query.filter(AlertNotification.triggered_at <= end_date)

    total = query.count()

    offset = (page - 1) * page_size
    notifications = (
        query.order_by(AlertNotification.triggered_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AlertNotificationListResponse(notifications=notifications, total=total)


@router.post("/check", status_code=202)
def trigger_check(db: Session = Depends(get_db)):
    """Manually trigger a check of all active alert rules."""
    engine = AlertEngine(session=db)
    try:
        triggered = engine.check_all_rules()
        return {
            "status": "completed",
            "alerts_triggered": len(triggered),
            "details": [
                {
                    "rule_id": n.rule_id,
                    "entity_id": n.entity_id,
                    "factor_value": n.factor_value,
                }
                for n in triggered
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

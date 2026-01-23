"""Admin API routes."""

import csv
import io
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.entity_mappings import (
    EntityMapping,
    MappingSuggestion,
    MappingStatus,
    SuggestionStatus,
    CorporateAction,
    CorporateActionType,
    CorporateActionStatus,
    MappingAuditLog,
    AuditActionType,
    Notification,
    NotificationType,
    NotificationChannel,
    CoverageSnapshot,
    EntityTradingMetrics,
)
from src.models.data_sources import (
    DataSource,
    DataSourceRequest,
    RequestStatus,
    CollectorHealthLog,
    CollectorStatus,
)

router = APIRouter()


# Pydantic schemas
class PendingMappingResponse(BaseModel):
    """Response for pending entity mapping."""

    id: int
    source_name: str
    source_entity_id: str
    source_entity_name: str
    suggested_ticker: Optional[str]
    confidence_score: float
    ai_suggestions: Optional[list]
    status: MappingStatus

    class Config:
        from_attributes = True


class MappingDecision(BaseModel):
    """Decision on a pending mapping."""

    action: str = Field(..., pattern="^(approve|reject|correct)$")
    ticker: Optional[str] = None  # Required for correct action
    notes: Optional[str] = None


class CoverageStats(BaseModel):
    """Entity mapping coverage statistics."""

    source_id: int
    source_name: str
    total_entities: int
    mapped_entities: int
    coverage_pct: float
    high_confidence_unmapped: int


class CollectorHealthResponse(BaseModel):
    """Health status for a collector."""

    source_id: int
    collector_name: str
    status: str  # up, down, degraded
    last_success: Optional[datetime]
    last_run: Optional[datetime]
    last_error: Optional[str]
    error_count_24h: int = 0
    success_count_24h: int = 0
    freshness_hours: float
    sla_hours: float
    sla_breach: bool
    records_collected_24h: int = 0
    avg_duration_seconds: Optional[float] = None


class CollectorHealthDetailResponse(BaseModel):
    """Detailed health status with error logs."""

    source_id: int
    collector_name: str
    status: str
    last_success: Optional[datetime]
    last_run: Optional[datetime]
    error_count_24h: int
    success_count_24h: int
    freshness_hours: float
    sla_hours: float
    sla_breach: bool
    recent_errors: list[dict]  # Recent error logs with stack traces
    run_history: list[dict]  # Recent run history


class CollectorTriggerResponse(BaseModel):
    """Response for manual collector trigger."""

    status: str
    source_id: int
    source_name: str
    task_id: str
    triggered_at: datetime
    triggered_by: str


# US-033: Source Request Admin Schemas
class SourceRequestUpdateStatus(BaseModel):
    """Update status for a data source request."""

    status: str = Field(..., pattern="^(under_review|approved|rejected|in_progress|completed)$")
    notes: Optional[str] = None


# US-035: Source Archive Schemas
class SourceArchiveRequest(BaseModel):
    """Request to archive a data source."""

    reason: str = Field(..., min_length=10)
    alternative_source_id: Optional[int] = None


class ArchivedSourceResponse(BaseModel):
    """Response for archived source."""

    id: int
    name: str
    description: str
    archived_at: datetime
    archived_reason: str
    alternative_source_id: Optional[int]
    alternative_source_name: Optional[str]
    factors_count: int  # Number of factors using this source

    class Config:
        from_attributes = True


# US-027: Audit Trail Schemas
class AuditLogEntry(BaseModel):
    """Audit log entry response."""

    id: int
    mapping_id: int
    user_id: Optional[int]
    action: str
    old_value: Optional[dict]
    new_value: Optional[dict]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# US-028: Notification Schemas
class NotificationResponse(BaseModel):
    """Notification response."""

    id: int
    user_id: int
    notification_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    """Create notification request."""

    user_id: int
    notification_type: str
    title: str
    message: str
    channels: list[str] = ["in_app"]
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None


# US-029: Coverage Analytics Schemas
class CoverageStatsExtended(BaseModel):
    """Extended entity mapping coverage statistics."""

    source_id: int
    source_name: str
    total_entities: int
    mapped_entities: int
    coverage_pct: float
    high_confidence_unmapped: int
    unmapped_value_usd: Optional[float] = None
    unmapped_volume: Optional[float] = None
    top_unmapped_by_value: Optional[list] = None


class CoverageTrendPoint(BaseModel):
    """Single point in coverage trend."""

    snapshot_date: datetime
    coverage_pct: float
    mapped_entities: int
    total_entities: int


class UnmappedEntityResponse(BaseModel):
    """Unmapped entity with prioritization info."""

    source_entity_id: str
    source_entity_name: str
    source_id: int
    source_name: str
    priority_score: float
    market_cap_usd: Optional[float] = None
    avg_daily_volume: Optional[float] = None
    suggested_ticker: Optional[str] = None
    confidence_score: float


# US-030: Corporate Action Schemas
class CorporateActionResponse(BaseModel):
    """Corporate action response."""

    id: int
    action_type: str
    old_ticker: str
    new_ticker: Optional[str]
    effective_date: datetime
    announcement_date: Optional[datetime]
    description: str
    status: str
    affected_mappings_count: int
    related_tickers: Optional[list]
    adjustment_factor: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class CorporateActionCreate(BaseModel):
    """Create corporate action request."""

    action_type: str
    old_ticker: str
    new_ticker: Optional[str] = None
    effective_date: datetime
    announcement_date: Optional[datetime] = None
    description: str
    related_tickers: Optional[list] = None
    adjustment_factor: Optional[float] = None


class CorporateActionDecision(BaseModel):
    """Decision on a corporate action."""

    action: str = Field(..., pattern="^(approve|reject)$")
    notes: Optional[str] = None


class AffectedMappingResponse(BaseModel):
    """Mapping affected by corporate action."""

    mapping_id: int
    source_entity_name: str
    current_ticker: str
    proposed_ticker: Optional[str]
    source_name: str


class HistoricalImpactPreview(BaseModel):
    """Preview of historical adjustment impact."""

    corporate_action_id: int
    affected_mappings: list[AffectedMappingResponse]
    total_affected: int
    adjustment_factor: Optional[float]
    description: str


# Routes
@router.get("/mappings/pending", response_model=list[PendingMappingResponse])
async def get_pending_mappings(
    source_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get pending entity mappings for review."""
    query = (
        select(EntityMapping, DataSource.name)
        .join(DataSource, EntityMapping.source_id == DataSource.id)
        .where(EntityMapping.status == MappingStatus.NEEDS_REVIEW)
    )

    if source_id:
        query = query.where(EntityMapping.source_id == source_id)

    query = query.order_by(EntityMapping.confidence_score.desc()).limit(limit)

    result = await db.execute(query)
    mappings = result.all()

    return [
        PendingMappingResponse(
            id=m.EntityMapping.id,
            source_name=m.name,
            source_entity_id=m.EntityMapping.source_entity_id,
            source_entity_name=m.EntityMapping.source_entity_name,
            suggested_ticker=m.EntityMapping.ticker,
            confidence_score=float(m.EntityMapping.confidence_score),
            ai_suggestions=m.EntityMapping.ai_suggestions,
            status=m.EntityMapping.status,
        )
        for m in mappings
    ]


@router.post("/mappings/{mapping_id}/decide")
async def decide_mapping(
    mapping_id: int,
    decision: MappingDecision,
    db: AsyncSession = Depends(get_db),
    # TODO: Add admin auth
):
    """Approve, reject, or correct a pending mapping."""
    query = select(EntityMapping).where(EntityMapping.id == mapping_id)
    result = await db.execute(query)
    mapping = result.scalar_one_or_none()

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found",
        )

    if decision.action == "approve":
        mapping.status = MappingStatus.MANUAL_APPROVED
    elif decision.action == "reject":
        mapping.status = MappingStatus.REJECTED
        mapping.ticker = None
    elif decision.action == "correct":
        if not decision.ticker:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ticker required for correct action",
            )
        mapping.ticker = decision.ticker.upper()
        mapping.status = MappingStatus.MANUAL_APPROVED
        mapping.confidence_score = 1.0

    mapping.reviewed_at = datetime.utcnow()
    mapping.review_notes = decision.notes
    # mapping.reviewed_by_user_id = current_user.id  # TODO

    await db.commit()

    return {"status": "updated", "mapping_id": mapping_id, "new_status": mapping.status.value}


@router.post("/mappings/bulk-approve")
async def bulk_approve_mappings(
    min_confidence: float = Query(0.9, ge=0, le=1),
    source_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Bulk approve high-confidence mappings."""
    query = (
        select(EntityMapping)
        .where(EntityMapping.status == MappingStatus.PENDING)
        .where(EntityMapping.confidence_score >= min_confidence)
    )

    if source_id:
        query = query.where(EntityMapping.source_id == source_id)

    result = await db.execute(query)
    mappings = result.scalars().all()

    for mapping in mappings:
        mapping.status = MappingStatus.AUTO_APPROVED
        mapping.reviewed_at = datetime.utcnow()

    await db.commit()

    return {"status": "bulk_approved", "count": len(mappings)}


@router.get("/mappings/coverage", response_model=list[CoverageStats])
async def get_mapping_coverage(
    db: AsyncSession = Depends(get_db),
):
    """Get entity mapping coverage statistics by source."""
    # Get total counts
    total_query = (
        select(
            EntityMapping.source_id,
            DataSource.name,
            func.count(EntityMapping.id).label("total"),
            func.count(EntityMapping.ticker).label("mapped"),
        )
        .join(DataSource, EntityMapping.source_id == DataSource.id)
        .group_by(EntityMapping.source_id, DataSource.name)
    )

    result = await db.execute(total_query)
    stats = result.all()

    return [
        CoverageStats(
            source_id=s.source_id,
            source_name=s.name,
            total_entities=s.total,
            mapped_entities=s.mapped,
            coverage_pct=(s.mapped / s.total * 100) if s.total > 0 else 0,
            high_confidence_unmapped=0,  # TODO: Calculate
        )
        for s in stats
    ]


@router.get("/collectors/health", response_model=list[CollectorHealthResponse])
async def get_collector_health(
    db: AsyncSession = Depends(get_db),
):
    """
    Get health status of all data collectors (US-034).

    Returns real-time health data including:
    - Up/down status based on recent runs
    - Last success timestamp
    - Error counts in last 24 hours
    - Data freshness vs SLA
    """
    query = select(DataSource).where(DataSource.is_active == True)
    result = await db.execute(query)
    sources = result.scalars().all()

    health_responses = []
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)

    for source in sources:
        # Get the most recent successful run
        last_success_query = (
            select(CollectorHealthLog)
            .where(CollectorHealthLog.source_id == source.id)
            .where(CollectorHealthLog.is_success == True)
            .order_by(desc(CollectorHealthLog.run_completed_at))
            .limit(1)
        )
        last_success_result = await db.execute(last_success_query)
        last_success_log = last_success_result.scalar_one_or_none()

        # Get the most recent run (success or failure)
        last_run_query = (
            select(CollectorHealthLog)
            .where(CollectorHealthLog.source_id == source.id)
            .order_by(desc(CollectorHealthLog.run_started_at))
            .limit(1)
        )
        last_run_result = await db.execute(last_run_query)
        last_run_log = last_run_result.scalar_one_or_none()

        # Count successes and failures in last 24h
        success_count_query = (
            select(func.count(CollectorHealthLog.id))
            .where(CollectorHealthLog.source_id == source.id)
            .where(CollectorHealthLog.is_success == True)
            .where(CollectorHealthLog.run_started_at >= last_24h)
        )
        success_count_result = await db.execute(success_count_query)
        success_count = success_count_result.scalar() or 0

        error_count_query = (
            select(func.count(CollectorHealthLog.id))
            .where(CollectorHealthLog.source_id == source.id)
            .where(CollectorHealthLog.is_success == False)
            .where(CollectorHealthLog.run_started_at >= last_24h)
        )
        error_count_result = await db.execute(error_count_query)
        error_count = error_count_result.scalar() or 0

        # Get records collected in last 24h
        records_query = (
            select(func.sum(CollectorHealthLog.records_collected))
            .where(CollectorHealthLog.source_id == source.id)
            .where(CollectorHealthLog.run_started_at >= last_24h)
        )
        records_result = await db.execute(records_query)
        records_collected = records_result.scalar() or 0

        # Get average duration
        avg_duration_query = (
            select(func.avg(CollectorHealthLog.duration_seconds))
            .where(CollectorHealthLog.source_id == source.id)
            .where(CollectorHealthLog.run_started_at >= last_24h)
            .where(CollectorHealthLog.duration_seconds.isnot(None))
        )
        avg_duration_result = await db.execute(avg_duration_query)
        avg_duration = avg_duration_result.scalar()

        # Determine status based on recent runs
        if not last_run_log:
            # No runs recorded yet
            collector_status = "degraded"
        elif last_run_log.is_success:
            collector_status = "up"
        elif error_count > 3:
            collector_status = "down"
        else:
            collector_status = "degraded"

        # Calculate freshness hours
        last_success_time = (
            last_success_log.run_completed_at if last_success_log else None
        )
        freshness_hours = 0.0
        if last_success_time:
            freshness_hours = (now - last_success_time).total_seconds() / 3600

        # SLA is typically 2x the expected latency
        sla_hours = source.latency_hours * 2
        sla_breach = freshness_hours > sla_hours

        # Get last error message
        last_error = None
        if last_run_log and not last_run_log.is_success:
            last_error = last_run_log.error_message

        health_responses.append(
            CollectorHealthResponse(
                source_id=source.id,
                collector_name=source.name,
                status=collector_status,
                last_success=last_success_time,
                last_run=last_run_log.run_started_at if last_run_log else None,
                last_error=last_error,
                error_count_24h=error_count,
                success_count_24h=success_count,
                freshness_hours=round(freshness_hours, 2),
                sla_hours=sla_hours,
                sla_breach=sla_breach,
                records_collected_24h=records_collected,
                avg_duration_seconds=round(avg_duration, 2) if avg_duration else None,
            )
        )

    return health_responses


@router.get("/collectors/{source_id}/health", response_model=CollectorHealthDetailResponse)
async def get_collector_health_detail(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed health status for a specific collector (US-034).

    Returns detailed information including:
    - Recent error logs with stack traces
    - Run history
    """
    # Verify source exists
    source_query = select(DataSource).where(DataSource.id == source_id)
    source_result = await db.execute(source_query)
    source = source_result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found",
        )

    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)

    # Get recent error logs
    error_logs_query = (
        select(CollectorHealthLog)
        .where(CollectorHealthLog.source_id == source_id)
        .where(CollectorHealthLog.is_success == False)
        .order_by(desc(CollectorHealthLog.run_started_at))
        .limit(10)
    )
    error_logs_result = await db.execute(error_logs_query)
    error_logs = error_logs_result.scalars().all()

    recent_errors = [
        {
            "run_started_at": log.run_started_at.isoformat() if log.run_started_at else None,
            "error_message": log.error_message,
            "error_stack_trace": log.error_stack_trace,
            "triggered_by": log.triggered_by,
        }
        for log in error_logs
    ]

    # Get run history (last 20 runs)
    history_query = (
        select(CollectorHealthLog)
        .where(CollectorHealthLog.source_id == source_id)
        .order_by(desc(CollectorHealthLog.run_started_at))
        .limit(20)
    )
    history_result = await db.execute(history_query)
    history_logs = history_result.scalars().all()

    run_history = [
        {
            "run_started_at": log.run_started_at.isoformat() if log.run_started_at else None,
            "run_completed_at": log.run_completed_at.isoformat() if log.run_completed_at else None,
            "is_success": log.is_success,
            "records_collected": log.records_collected,
            "duration_seconds": log.duration_seconds,
            "triggered_by": log.triggered_by,
        }
        for log in history_logs
    ]

    # Get aggregated stats
    last_success_query = (
        select(CollectorHealthLog)
        .where(CollectorHealthLog.source_id == source_id)
        .where(CollectorHealthLog.is_success == True)
        .order_by(desc(CollectorHealthLog.run_completed_at))
        .limit(1)
    )
    last_success_result = await db.execute(last_success_query)
    last_success_log = last_success_result.scalar_one_or_none()

    last_run_query = (
        select(CollectorHealthLog)
        .where(CollectorHealthLog.source_id == source_id)
        .order_by(desc(CollectorHealthLog.run_started_at))
        .limit(1)
    )
    last_run_result = await db.execute(last_run_query)
    last_run_log = last_run_result.scalar_one_or_none()

    # Counts
    success_count_query = (
        select(func.count(CollectorHealthLog.id))
        .where(CollectorHealthLog.source_id == source_id)
        .where(CollectorHealthLog.is_success == True)
        .where(CollectorHealthLog.run_started_at >= last_24h)
    )
    success_count_result = await db.execute(success_count_query)
    success_count = success_count_result.scalar() or 0

    error_count_query = (
        select(func.count(CollectorHealthLog.id))
        .where(CollectorHealthLog.source_id == source_id)
        .where(CollectorHealthLog.is_success == False)
        .where(CollectorHealthLog.run_started_at >= last_24h)
    )
    error_count_result = await db.execute(error_count_query)
    error_count = error_count_result.scalar() or 0

    # Determine status
    if not last_run_log:
        collector_status = "degraded"
    elif last_run_log.is_success:
        collector_status = "up"
    elif error_count > 3:
        collector_status = "down"
    else:
        collector_status = "degraded"

    # Calculate freshness
    last_success_time = last_success_log.run_completed_at if last_success_log else None
    freshness_hours = 0.0
    if last_success_time:
        freshness_hours = (now - last_success_time).total_seconds() / 3600

    sla_hours = source.latency_hours * 2
    sla_breach = freshness_hours > sla_hours

    return CollectorHealthDetailResponse(
        source_id=source.id,
        collector_name=source.name,
        status=collector_status,
        last_success=last_success_time,
        last_run=last_run_log.run_started_at if last_run_log else None,
        error_count_24h=error_count,
        success_count_24h=success_count,
        freshness_hours=round(freshness_hours, 2),
        sla_hours=sla_hours,
        sla_breach=sla_breach,
        recent_errors=recent_errors,
        run_history=run_history,
    )


@router.post("/collectors/{source_id}/trigger", response_model=CollectorTriggerResponse)
async def trigger_collector(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    # TODO: Add admin auth
):
    """
    Manually trigger a collector run (US-034).

    Creates a health log entry to track the manual run.
    In production, this would trigger the actual collector via Celery.
    """
    query = select(DataSource).where(DataSource.id == source_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found",
        )

    # Generate task ID
    task_id = str(uuid.uuid4())
    now = datetime.utcnow()

    # Create health log entry for manual trigger
    health_log = CollectorHealthLog(
        source_id=source_id,
        run_started_at=now,
        status=CollectorStatus.UP,
        is_success=False,  # Will be updated when run completes
        sla_hours=source.latency_hours * 2,
        triggered_by="manual",
        triggered_by_user_id=1,  # TODO: Get from authenticated user
        task_id=task_id,
    )

    db.add(health_log)
    await db.flush()

    # TODO: Trigger actual collector via Celery
    # Example: celery_app.send_task('collectors.run', args=[source.name, health_log.id])

    return CollectorTriggerResponse(
        status="triggered",
        source_id=source_id,
        source_name=source.name,
        task_id=task_id,
        triggered_at=now,
        triggered_by="manual",
    )


@router.get("/suggestions/pending")
async def get_pending_suggestions(
    source_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get pending mapping suggestions from users."""
    query = (
        select(MappingSuggestion)
        .where(MappingSuggestion.status == SuggestionStatus.SUBMITTED)
    )

    if source_id:
        query = query.where(MappingSuggestion.source_id == source_id)

    query = query.order_by(MappingSuggestion.created_at.desc()).limit(limit)

    result = await db.execute(query)
    suggestions = result.scalars().all()

    return [
        {
            "id": s.id,
            "source_entity_name": s.source_entity_name,
            "suggested_ticker": s.suggested_ticker,
            "confidence": float(s.confidence),
            "rationale": s.rationale,
            "submitted_at": s.created_at,
        }
        for s in suggestions
    ]


# US-033: Data Source Request Admin Endpoints
@router.patch("/requests/{request_id}/status")
async def update_source_request_status(
    request_id: int,
    status_update: SourceRequestUpdateStatus,
    db: AsyncSession = Depends(get_db),
    # TODO: Add admin auth
):
    """
    Update the status of a data source request (US-033).

    Sends notification to the requester when status changes.
    """
    query = select(DataSourceRequest).where(DataSourceRequest.id == request_id)
    result = await db.execute(query)
    source_request = result.scalar_one_or_none()

    if not source_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source request {request_id} not found",
        )

    # Map string status to enum
    status_map = {
        "under_review": RequestStatus.UNDER_REVIEW,
        "approved": RequestStatus.APPROVED,
        "rejected": RequestStatus.REJECTED,
        "in_progress": RequestStatus.IN_PROGRESS,
        "completed": RequestStatus.COMPLETED,
    }

    old_status = source_request.status
    new_status = status_map.get(status_update.status)

    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {status_update.status}",
        )

    source_request.status = new_status
    source_request.reviewed_at = datetime.utcnow()
    source_request.review_notes = status_update.notes
    source_request.reviewed_by_user_id = 1  # TODO: Get from authenticated user

    await db.flush()

    # TODO: Send notification to requester about status change
    # Example: await send_notification(source_request.requester_id, f"Your request '{source_request.name}' status changed to {new_status.value}")

    return {
        "status": "updated",
        "request_id": request_id,
        "old_status": old_status.value,
        "new_status": new_status.value,
    }


# US-035: Source Archival Endpoints
@router.post("/sources/{source_id}/archive", response_model=ArchivedSourceResponse)
async def archive_source(
    source_id: int,
    archive_request: SourceArchiveRequest,
    db: AsyncSession = Depends(get_db),
    # TODO: Add admin auth
):
    """
    Archive a data source (US-035).

    Archives the source while maintaining full API access to historical data.
    Factors from archived sources remain computable.
    Optionally links to an alternative source.
    """
    query = select(DataSource).where(DataSource.id == source_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found",
        )

    if source.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data source {source_id} is already archived",
        )

    # Validate alternative source if provided
    alternative_source_name = None
    if archive_request.alternative_source_id:
        alt_query = select(DataSource).where(
            DataSource.id == archive_request.alternative_source_id
        )
        alt_result = await db.execute(alt_query)
        alt_source = alt_result.scalar_one_or_none()

        if not alt_source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alternative source {archive_request.alternative_source_id} not found",
            )

        if alt_source.is_archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Alternative source cannot be an archived source",
            )

        alternative_source_name = alt_source.name

    # Count factors using this source
    from src.models.factors import Factor

    factors_query = select(func.count(Factor.id)).where(Factor.source_id == source_id)
    factors_result = await db.execute(factors_query)
    factors_count = factors_result.scalar() or 0

    # Archive the source
    source.is_archived = True
    source.archived_at = datetime.utcnow()
    source.archived_reason = archive_request.reason
    source.alternative_source_id = archive_request.alternative_source_id
    # Keep is_active=True to maintain API access

    await db.flush()

    return ArchivedSourceResponse(
        id=source.id,
        name=source.name,
        description=source.description,
        archived_at=source.archived_at,
        archived_reason=source.archived_reason,
        alternative_source_id=source.alternative_source_id,
        alternative_source_name=alternative_source_name,
        factors_count=factors_count,
    )


@router.get("/sources/archived", response_model=list[ArchivedSourceResponse])
async def list_archived_sources(
    db: AsyncSession = Depends(get_db),
):
    """
    List all archived data sources (US-035).

    Returns archived sources with alternative source information.
    """
    query = select(DataSource).where(DataSource.is_archived == True)
    result = await db.execute(query)
    sources = result.scalars().all()

    responses = []
    for source in sources:
        # Get alternative source name if linked
        alternative_source_name = None
        if source.alternative_source_id:
            alt_query = select(DataSource.name).where(
                DataSource.id == source.alternative_source_id
            )
            alt_result = await db.execute(alt_query)
            alternative_source_name = alt_result.scalar()

        # Count factors
        from src.models.factors import Factor

        factors_query = select(func.count(Factor.id)).where(Factor.source_id == source.id)
        factors_result = await db.execute(factors_query)
        factors_count = factors_result.scalar() or 0

        responses.append(
            ArchivedSourceResponse(
                id=source.id,
                name=source.name,
                description=source.description,
                archived_at=source.archived_at,
                archived_reason=source.archived_reason,
                alternative_source_id=source.alternative_source_id,
                alternative_source_name=alternative_source_name,
                factors_count=factors_count,
            )
        )

    return responses


@router.post("/sources/{source_id}/unarchive")
async def unarchive_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    # TODO: Add admin auth
):
    """
    Unarchive a data source (US-035).

    Restores an archived source to active status.
    """
    query = select(DataSource).where(DataSource.id == source_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found",
        )

    if not source.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data source {source_id} is not archived",
        )

    source.is_archived = False
    source.archived_at = None
    source.archived_reason = None
    source.alternative_source_id = None

    await db.flush()

    return {
        "status": "unarchived",
        "source_id": source_id,
        "source_name": source.name,
    }


# =============================================================================
# US-027: Audit Trail for Entity Mappings
# =============================================================================

async def create_audit_log(
    db: AsyncSession,
    mapping_id: int,
    action: AuditActionType,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
    user_id: Optional[int] = None,
    notes: Optional[str] = None,
    request: Optional[Request] = None,
) -> MappingAuditLog:
    """Create an audit log entry for a mapping change."""
    audit_log = MappingAuditLog(
        mapping_id=mapping_id,
        user_id=user_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        notes=notes,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    db.add(audit_log)
    return audit_log


@router.get("/mappings/{mapping_id}/audit", response_model=list[AuditLogEntry])
async def get_mapping_audit_history(
    mapping_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Get audit history for a specific mapping (US-027)."""
    # Verify mapping exists
    mapping_query = select(EntityMapping).where(EntityMapping.id == mapping_id)
    result = await db.execute(mapping_query)
    mapping = result.scalar_one_or_none()

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found",
        )

    # Get audit logs
    query = (
        select(MappingAuditLog)
        .where(MappingAuditLog.mapping_id == mapping_id)
        .order_by(desc(MappingAuditLog.created_at))
        .limit(limit)
    )

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        AuditLogEntry(
            id=log.id,
            mapping_id=log.mapping_id,
            user_id=log.user_id,
            action=log.action.value,
            old_value=log.old_value,
            new_value=log.new_value,
            notes=log.notes,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.post("/mappings/{mapping_id}/decide/audited")
async def decide_mapping_with_audit(
    mapping_id: int,
    decision: MappingDecision,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Approve, reject, or correct a pending mapping with audit trail (US-027)."""
    query = select(EntityMapping).where(EntityMapping.id == mapping_id)
    result = await db.execute(query)
    mapping = result.scalar_one_or_none()

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found",
        )

    # Capture old state for audit
    old_value = {
        "status": mapping.status.value,
        "ticker": mapping.ticker,
        "confidence_score": float(mapping.confidence_score),
    }

    # Determine action type for audit
    action_type = AuditActionType.UPDATE
    if decision.action == "approve":
        mapping.status = MappingStatus.MANUAL_APPROVED
        action_type = AuditActionType.APPROVE
    elif decision.action == "reject":
        mapping.status = MappingStatus.REJECTED
        mapping.ticker = None
        action_type = AuditActionType.REJECT
    elif decision.action == "correct":
        if not decision.ticker:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ticker required for correct action",
            )
        mapping.ticker = decision.ticker.upper()
        mapping.status = MappingStatus.MANUAL_APPROVED
        mapping.confidence_score = Decimal("1.0")
        action_type = AuditActionType.CORRECT

    mapping.reviewed_at = datetime.utcnow()
    mapping.review_notes = decision.notes

    # Capture new state for audit
    new_value = {
        "status": mapping.status.value,
        "ticker": mapping.ticker,
        "confidence_score": float(mapping.confidence_score),
    }

    # Create audit log
    await create_audit_log(
        db=db,
        mapping_id=mapping_id,
        action=action_type,
        old_value=old_value,
        new_value=new_value,
        notes=decision.notes,
        request=request,
    )

    # Dispatch notification for status change
    await dispatch_mapping_notification(
        db=db,
        mapping=mapping,
        old_status=old_value["status"],
        new_status=mapping.status.value,
    )

    await db.commit()

    return {
        "status": "updated",
        "mapping_id": mapping_id,
        "new_status": mapping.status.value,
        "audit_logged": True,
    }


# =============================================================================
# US-028: Notification on Mapping Status Change
# =============================================================================

async def dispatch_mapping_notification(
    db: AsyncSession,
    mapping: EntityMapping,
    old_status: str,
    new_status: str,
):
    """Dispatch notification when mapping status changes (US-028)."""
    # Get the user who submitted the mapping or suggestion
    user_id = mapping.reviewed_by_user_id

    if not user_id:
        # For now, skip notification if no user associated
        return

    title = f"Mapping Status Changed: {mapping.source_entity_name}"
    message = (
        f"The mapping for '{mapping.source_entity_name}' has been updated.\n"
        f"Status changed from '{old_status}' to '{new_status}'."
    )
    if mapping.ticker:
        message += f"\nTicker: {mapping.ticker}"

    notification = Notification(
        user_id=user_id,
        notification_type=NotificationType.MAPPING_STATUS_CHANGE,
        title=title,
        message=message,
        channels=[NotificationChannel.IN_APP.value, NotificationChannel.EMAIL.value],
        related_entity_type="entity_mapping",
        related_entity_id=mapping.id,
    )
    db.add(notification)


@router.post("/notifications", response_model=NotificationResponse)
async def create_notification(
    notification_data: NotificationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new notification (US-028)."""
    notification = Notification(
        user_id=notification_data.user_id,
        notification_type=NotificationType(notification_data.notification_type),
        title=notification_data.title,
        message=notification_data.message,
        channels=notification_data.channels,
        related_entity_type=notification_data.related_entity_type,
        related_entity_id=notification_data.related_entity_id,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        notification_type=notification.notification_type.value,
        title=notification.title,
        message=notification.message,
        is_read=notification.is_read,
        created_at=notification.created_at,
    )


@router.get("/notifications/user/{user_id}", response_model=list[NotificationResponse])
async def get_user_notifications(
    user_id: int,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get notifications for a user (US-028)."""
    query = select(Notification).where(Notification.user_id == user_id)

    if unread_only:
        query = query.where(Notification.is_read == False)

    query = query.order_by(desc(Notification.created_at)).limit(limit)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return [
        NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            notification_type=n.notification_type.value,
            title=n.title,
            message=n.message,
            is_read=n.is_read,
            created_at=n.created_at,
        )
        for n in notifications
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read (US-028)."""
    query = select(Notification).where(Notification.id == notification_id)
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )

    notification.is_read = True
    notification.read_at = datetime.utcnow()
    await db.commit()

    return {"status": "marked_read", "notification_id": notification_id}


# =============================================================================
# US-029: Coverage Analytics
# =============================================================================

@router.get("/mappings/coverage/extended", response_model=list[CoverageStatsExtended])
async def get_extended_mapping_coverage(
    db: AsyncSession = Depends(get_db),
):
    """Get extended entity mapping coverage with value/volume metrics (US-029)."""
    # Get basic coverage stats
    basic_query = (
        select(
            EntityMapping.source_id,
            DataSource.name,
            func.count(EntityMapping.id).label("total"),
            func.count(EntityMapping.ticker).label("mapped"),
        )
        .join(DataSource, EntityMapping.source_id == DataSource.id)
        .group_by(EntityMapping.source_id, DataSource.name)
    )

    result = await db.execute(basic_query)
    stats = result.all()

    extended_stats = []
    for s in stats:
        # Get high-confidence unmapped count
        unmapped_query = (
            select(func.count(EntityMapping.id))
            .where(EntityMapping.source_id == s.source_id)
            .where(EntityMapping.ticker.is_(None))
            .where(EntityMapping.confidence_score >= 0.8)
        )
        unmapped_result = await db.execute(unmapped_query)
        high_conf_unmapped = unmapped_result.scalar() or 0

        # Get value/volume metrics for unmapped entities
        value_query = (
            select(
                func.sum(EntityTradingMetrics.avg_daily_value_usd).label("total_value"),
                func.sum(EntityTradingMetrics.avg_daily_volume).label("total_volume"),
            )
            .join(
                EntityMapping,
                and_(
                    EntityTradingMetrics.source_id == EntityMapping.source_id,
                    EntityTradingMetrics.source_entity_id == EntityMapping.source_entity_id,
                ),
            )
            .where(EntityMapping.source_id == s.source_id)
            .where(EntityMapping.ticker.is_(None))
        )
        value_result = await db.execute(value_query)
        value_data = value_result.first()

        # Get top unmapped by value
        top_unmapped_query = (
            select(
                EntityMapping.source_entity_id,
                EntityMapping.source_entity_name,
                EntityTradingMetrics.priority_score,
            )
            .join(
                EntityTradingMetrics,
                and_(
                    EntityMapping.source_id == EntityTradingMetrics.source_id,
                    EntityMapping.source_entity_id == EntityTradingMetrics.source_entity_id,
                ),
            )
            .where(EntityMapping.source_id == s.source_id)
            .where(EntityMapping.ticker.is_(None))
            .order_by(desc(EntityTradingMetrics.priority_score))
            .limit(5)
        )
        top_result = await db.execute(top_unmapped_query)
        top_unmapped = [
            {
                "entity_id": r.source_entity_id,
                "entity_name": r.source_entity_name,
                "priority_score": float(r.priority_score) if r.priority_score else 0,
            }
            for r in top_result.all()
        ]

        extended_stats.append(
            CoverageStatsExtended(
                source_id=s.source_id,
                source_name=s.name,
                total_entities=s.total,
                mapped_entities=s.mapped,
                coverage_pct=(s.mapped / s.total * 100) if s.total > 0 else 0,
                high_confidence_unmapped=high_conf_unmapped,
                unmapped_value_usd=float(value_data.total_value) if value_data and value_data.total_value else None,
                unmapped_volume=float(value_data.total_volume) if value_data and value_data.total_volume else None,
                top_unmapped_by_value=top_unmapped if top_unmapped else None,
            )
        )

    return extended_stats


@router.get("/mappings/coverage/trend/{source_id}", response_model=list[CoverageTrendPoint])
async def get_coverage_trend(
    source_id: int,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get coverage trend over time for a source (US-029)."""
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    query = (
        select(CoverageSnapshot)
        .where(CoverageSnapshot.source_id == source_id)
        .where(CoverageSnapshot.snapshot_date >= cutoff_date)
        .order_by(CoverageSnapshot.snapshot_date)
    )

    result = await db.execute(query)
    snapshots = result.scalars().all()

    return [
        CoverageTrendPoint(
            snapshot_date=s.snapshot_date,
            coverage_pct=float(s.coverage_pct),
            mapped_entities=s.mapped_entities,
            total_entities=s.total_entities,
        )
        for s in snapshots
    ]


@router.post("/mappings/coverage/snapshot")
async def create_coverage_snapshot(
    source_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a coverage snapshot for trend tracking (US-029)."""
    # Get all sources or specific source
    if source_id:
        sources_query = select(DataSource).where(DataSource.id == source_id)
    else:
        sources_query = select(DataSource).where(DataSource.is_active == True)

    sources_result = await db.execute(sources_query)
    sources = sources_result.scalars().all()

    snapshots_created = []
    snapshot_time = datetime.utcnow()

    for source in sources:
        # Get coverage stats
        stats_query = (
            select(
                func.count(EntityMapping.id).label("total"),
                func.count(EntityMapping.ticker).label("mapped"),
            )
            .where(EntityMapping.source_id == source.id)
        )
        stats_result = await db.execute(stats_query)
        stats = stats_result.first()

        total = stats.total or 0
        mapped = stats.mapped or 0
        coverage_pct = (mapped / total * 100) if total > 0 else 0

        # Get value metrics
        value_query = (
            select(
                func.sum(EntityTradingMetrics.avg_daily_value_usd).label("total_value"),
                func.sum(EntityTradingMetrics.avg_daily_volume).label("total_volume"),
            )
            .where(EntityTradingMetrics.source_id == source.id)
        )
        value_result = await db.execute(value_query)
        value_data = value_result.first()

        # Compute unmapped value
        unmapped_value_query = (
            select(
                func.sum(EntityTradingMetrics.avg_daily_value_usd).label("unmapped_value"),
                func.sum(EntityTradingMetrics.avg_daily_volume).label("unmapped_volume"),
            )
            .join(
                EntityMapping,
                and_(
                    EntityTradingMetrics.source_id == EntityMapping.source_id,
                    EntityTradingMetrics.source_entity_id == EntityMapping.source_entity_id,
                ),
            )
            .where(EntityTradingMetrics.source_id == source.id)
            .where(EntityMapping.ticker.is_(None))
        )
        unmapped_result = await db.execute(unmapped_value_query)
        unmapped_data = unmapped_result.first()

        # Count high-value unmapped
        high_value_query = (
            select(func.count(EntityTradingMetrics.id))
            .join(
                EntityMapping,
                and_(
                    EntityTradingMetrics.source_id == EntityMapping.source_id,
                    EntityTradingMetrics.source_entity_id == EntityMapping.source_entity_id,
                ),
            )
            .where(EntityTradingMetrics.source_id == source.id)
            .where(EntityMapping.ticker.is_(None))
            .where(EntityTradingMetrics.priority_score >= 0.7)
        )
        high_value_result = await db.execute(high_value_query)
        high_value_count = high_value_result.scalar() or 0

        snapshot = CoverageSnapshot(
            source_id=source.id,
            snapshot_date=snapshot_time,
            total_entities=total,
            mapped_entities=mapped,
            coverage_pct=Decimal(str(coverage_pct)),
            total_value_usd=value_data.total_value if value_data else None,
            mapped_value_usd=(
                (value_data.total_value - unmapped_data.unmapped_value)
                if value_data and value_data.total_value and unmapped_data and unmapped_data.unmapped_value
                else None
            ),
            unmapped_value_usd=unmapped_data.unmapped_value if unmapped_data else None,
            total_volume=value_data.total_volume if value_data else None,
            mapped_volume=(
                (value_data.total_volume - unmapped_data.unmapped_volume)
                if value_data and value_data.total_volume and unmapped_data and unmapped_data.unmapped_volume
                else None
            ),
            unmapped_volume=unmapped_data.unmapped_volume if unmapped_data else None,
            high_value_unmapped_count=high_value_count,
        )
        db.add(snapshot)
        snapshots_created.append(source.id)

    await db.commit()

    return {
        "status": "snapshots_created",
        "count": len(snapshots_created),
        "source_ids": snapshots_created,
        "snapshot_time": snapshot_time,
    }


@router.get("/mappings/unmapped/prioritized", response_model=list[UnmappedEntityResponse])
async def get_prioritized_unmapped_entities(
    source_id: Optional[int] = None,
    min_priority: float = Query(0.0, ge=0, le=1),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Get unmapped entities prioritized by trading volume/value (US-029)."""
    query = (
        select(
            EntityMapping.source_entity_id,
            EntityMapping.source_entity_name,
            EntityMapping.source_id,
            EntityMapping.ticker.label("suggested_ticker"),
            EntityMapping.confidence_score,
            DataSource.name.label("source_name"),
            EntityTradingMetrics.priority_score,
            EntityTradingMetrics.market_cap_usd,
            EntityTradingMetrics.avg_daily_volume,
        )
        .join(DataSource, EntityMapping.source_id == DataSource.id)
        .outerjoin(
            EntityTradingMetrics,
            and_(
                EntityMapping.source_id == EntityTradingMetrics.source_id,
                EntityMapping.source_entity_id == EntityTradingMetrics.source_entity_id,
            ),
        )
        .where(EntityMapping.ticker.is_(None))
        .where(
            or_(
                EntityTradingMetrics.priority_score >= min_priority,
                EntityTradingMetrics.priority_score.is_(None),
            )
        )
    )

    if source_id:
        query = query.where(EntityMapping.source_id == source_id)

    query = query.order_by(
        desc(func.coalesce(EntityTradingMetrics.priority_score, 0))
    ).limit(limit)

    result = await db.execute(query)
    entities = result.all()

    return [
        UnmappedEntityResponse(
            source_entity_id=e.source_entity_id,
            source_entity_name=e.source_entity_name,
            source_id=e.source_id,
            source_name=e.source_name,
            priority_score=float(e.priority_score) if e.priority_score else 0.0,
            market_cap_usd=float(e.market_cap_usd) if e.market_cap_usd else None,
            avg_daily_volume=float(e.avg_daily_volume) if e.avg_daily_volume else None,
            suggested_ticker=e.suggested_ticker,
            confidence_score=float(e.confidence_score),
        )
        for e in entities
    ]


@router.get("/mappings/unmapped/export")
async def export_unmapped_entities_csv(
    source_id: Optional[int] = None,
    min_priority: float = Query(0.0, ge=0, le=1),
    db: AsyncSession = Depends(get_db),
):
    """Export unmapped entities as CSV (US-029)."""
    query = (
        select(
            EntityMapping.source_entity_id,
            EntityMapping.source_entity_name,
            EntityMapping.source_id,
            EntityMapping.confidence_score,
            DataSource.name.label("source_name"),
            EntityTradingMetrics.priority_score,
            EntityTradingMetrics.market_cap_usd,
            EntityTradingMetrics.avg_daily_volume,
            EntityTradingMetrics.avg_daily_value_usd,
        )
        .join(DataSource, EntityMapping.source_id == DataSource.id)
        .outerjoin(
            EntityTradingMetrics,
            and_(
                EntityMapping.source_id == EntityTradingMetrics.source_id,
                EntityMapping.source_entity_id == EntityTradingMetrics.source_entity_id,
            ),
        )
        .where(EntityMapping.ticker.is_(None))
    )

    if source_id:
        query = query.where(EntityMapping.source_id == source_id)

    if min_priority > 0:
        query = query.where(
            or_(
                EntityTradingMetrics.priority_score >= min_priority,
                EntityTradingMetrics.priority_score.is_(None),
            )
        )

    query = query.order_by(desc(func.coalesce(EntityTradingMetrics.priority_score, 0)))

    result = await db.execute(query)
    entities = result.all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "source_entity_id",
        "source_entity_name",
        "source_id",
        "source_name",
        "priority_score",
        "market_cap_usd",
        "avg_daily_volume",
        "avg_daily_value_usd",
        "confidence_score",
    ])

    # Data rows
    for e in entities:
        writer.writerow([
            e.source_entity_id,
            e.source_entity_name,
            e.source_id,
            e.source_name,
            float(e.priority_score) if e.priority_score else "",
            float(e.market_cap_usd) if e.market_cap_usd else "",
            float(e.avg_daily_volume) if e.avg_daily_volume else "",
            float(e.avg_daily_value_usd) if e.avg_daily_value_usd else "",
            float(e.confidence_score),
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=unmapped_entities_{datetime.utcnow().strftime('%Y%m%d')}.csv"
        },
    )


# =============================================================================
# US-030: Corporate Action Handling
# =============================================================================

@router.get("/corporate-actions", response_model=list[CorporateActionResponse])
async def list_corporate_actions(
    status_filter: Optional[str] = None,
    ticker: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List corporate actions (US-030)."""
    query = select(CorporateAction)

    if status_filter:
        query = query.where(CorporateAction.status == CorporateActionStatus(status_filter))

    if ticker:
        query = query.where(
            or_(
                CorporateAction.old_ticker == ticker.upper(),
                CorporateAction.new_ticker == ticker.upper(),
            )
        )

    query = query.order_by(desc(CorporateAction.effective_date)).limit(limit)

    result = await db.execute(query)
    actions = result.scalars().all()

    return [
        CorporateActionResponse(
            id=a.id,
            action_type=a.action_type.value,
            old_ticker=a.old_ticker,
            new_ticker=a.new_ticker,
            effective_date=a.effective_date,
            announcement_date=a.announcement_date,
            description=a.description,
            status=a.status.value,
            affected_mappings_count=a.affected_mappings_count,
            related_tickers=a.related_tickers,
            adjustment_factor=float(a.adjustment_factor) if a.adjustment_factor else None,
            created_at=a.created_at,
        )
        for a in actions
    ]


@router.post("/corporate-actions", response_model=CorporateActionResponse)
async def create_corporate_action(
    action_data: CorporateActionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new corporate action (US-030)."""
    # Count affected mappings
    affected_query = (
        select(func.count(EntityMapping.id))
        .where(EntityMapping.ticker == action_data.old_ticker.upper())
    )
    affected_result = await db.execute(affected_query)
    affected_count = affected_result.scalar() or 0

    corporate_action = CorporateAction(
        action_type=CorporateActionType(action_data.action_type),
        old_ticker=action_data.old_ticker.upper(),
        new_ticker=action_data.new_ticker.upper() if action_data.new_ticker else None,
        effective_date=action_data.effective_date,
        announcement_date=action_data.announcement_date,
        description=action_data.description,
        related_tickers=action_data.related_tickers,
        adjustment_factor=Decimal(str(action_data.adjustment_factor)) if action_data.adjustment_factor else None,
        status=CorporateActionStatus.DETECTED,
        affected_mappings_count=affected_count,
    )
    db.add(corporate_action)
    await db.commit()
    await db.refresh(corporate_action)

    return CorporateActionResponse(
        id=corporate_action.id,
        action_type=corporate_action.action_type.value,
        old_ticker=corporate_action.old_ticker,
        new_ticker=corporate_action.new_ticker,
        effective_date=corporate_action.effective_date,
        announcement_date=corporate_action.announcement_date,
        description=corporate_action.description,
        status=corporate_action.status.value,
        affected_mappings_count=corporate_action.affected_mappings_count,
        related_tickers=corporate_action.related_tickers,
        adjustment_factor=float(corporate_action.adjustment_factor) if corporate_action.adjustment_factor else None,
        created_at=corporate_action.created_at,
    )


@router.get("/corporate-actions/detect")
async def detect_corporate_actions(
    ticker: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Detect potential corporate actions affecting entity mappings (US-030).

    This endpoint checks for:
    - Mappings where ticker has changed recently
    - Known corporate action patterns in the database
    - Mappings that may need attention
    """
    potential_actions = []

    # Check for mappings with previous_ticker set (indicating potential corporate action)
    query = (
        select(EntityMapping, DataSource.name)
        .join(DataSource, EntityMapping.source_id == DataSource.id)
        .where(EntityMapping.previous_ticker.isnot(None))
    )

    if ticker:
        query = query.where(
            or_(
                EntityMapping.ticker == ticker.upper(),
                EntityMapping.previous_ticker == ticker.upper(),
            )
        )

    result = await db.execute(query)
    mappings_with_history = result.all()

    for m in mappings_with_history:
        # Check if there's already a corporate action for this
        existing_action_query = (
            select(CorporateAction)
            .where(CorporateAction.old_ticker == m.EntityMapping.previous_ticker)
            .where(CorporateAction.new_ticker == m.EntityMapping.ticker)
        )
        existing_result = await db.execute(existing_action_query)
        existing_action = existing_result.scalar_one_or_none()

        if not existing_action:
            potential_actions.append({
                "type": "ticker_change_detected",
                "mapping_id": m.EntityMapping.id,
                "source_name": m.name,
                "source_entity_name": m.EntityMapping.source_entity_name,
                "old_ticker": m.EntityMapping.previous_ticker,
                "new_ticker": m.EntityMapping.ticker,
                "suggested_action_type": "ticker_change",
            })

    return {
        "potential_actions_detected": len(potential_actions),
        "actions": potential_actions,
    }


@router.get("/corporate-actions/{action_id}/affected", response_model=list[AffectedMappingResponse])
async def get_affected_mappings(
    action_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get entity mappings affected by a corporate action (US-030)."""
    # Get the corporate action
    action_query = select(CorporateAction).where(CorporateAction.id == action_id)
    action_result = await db.execute(action_query)
    action = action_result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Corporate action {action_id} not found",
        )

    # Get affected mappings
    query = (
        select(EntityMapping, DataSource.name)
        .join(DataSource, EntityMapping.source_id == DataSource.id)
        .where(EntityMapping.ticker == action.old_ticker)
    )

    result = await db.execute(query)
    mappings = result.all()

    return [
        AffectedMappingResponse(
            mapping_id=m.EntityMapping.id,
            source_entity_name=m.EntityMapping.source_entity_name,
            current_ticker=m.EntityMapping.ticker,
            proposed_ticker=action.new_ticker,
            source_name=m.name,
        )
        for m in mappings
    ]


@router.get("/corporate-actions/{action_id}/preview", response_model=HistoricalImpactPreview)
async def preview_corporate_action_impact(
    action_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Preview the impact of applying a corporate action (US-030)."""
    # Get the corporate action
    action_query = select(CorporateAction).where(CorporateAction.id == action_id)
    action_result = await db.execute(action_query)
    action = action_result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Corporate action {action_id} not found",
        )

    # Get affected mappings
    query = (
        select(EntityMapping, DataSource.name)
        .join(DataSource, EntityMapping.source_id == DataSource.id)
        .where(EntityMapping.ticker == action.old_ticker)
    )

    result = await db.execute(query)
    mappings = result.all()

    affected_mappings = [
        AffectedMappingResponse(
            mapping_id=m.EntityMapping.id,
            source_entity_name=m.EntityMapping.source_entity_name,
            current_ticker=m.EntityMapping.ticker,
            proposed_ticker=action.new_ticker,
            source_name=m.name,
        )
        for m in mappings
    ]

    return HistoricalImpactPreview(
        corporate_action_id=action.id,
        affected_mappings=affected_mappings,
        total_affected=len(affected_mappings),
        adjustment_factor=float(action.adjustment_factor) if action.adjustment_factor else None,
        description=f"Applying this {action.action_type.value} will update {len(affected_mappings)} mappings "
                    f"from {action.old_ticker} to {action.new_ticker or 'N/A'}. "
                    f"Historical data will be preserved with version tracking.",
    )


@router.post("/corporate-actions/{action_id}/decide")
async def decide_corporate_action(
    action_id: int,
    decision: CorporateActionDecision,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a corporate action adjustment (US-030)."""
    # Get the corporate action
    action_query = select(CorporateAction).where(CorporateAction.id == action_id)
    action_result = await db.execute(action_query)
    action = action_result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Corporate action {action_id} not found",
        )

    if action.status not in [CorporateActionStatus.DETECTED, CorporateActionStatus.PENDING_REVIEW]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corporate action is already {action.status.value}",
        )

    if decision.action == "approve":
        action.status = CorporateActionStatus.APPROVED
        action.approved_at = datetime.utcnow()

        # Apply the corporate action to affected mappings
        update_query = (
            select(EntityMapping)
            .where(EntityMapping.ticker == action.old_ticker)
        )
        update_result = await db.execute(update_query)
        mappings_to_update = update_result.scalars().all()

        updated_count = 0
        for mapping in mappings_to_update:
            # Store old state
            old_value = {
                "ticker": mapping.ticker,
                "version": mapping.version,
            }

            # Update mapping
            mapping.previous_ticker = mapping.ticker
            mapping.ticker = action.new_ticker
            mapping.version += 1
            mapping.effective_from = action.effective_date

            # Create audit log
            await create_audit_log(
                db=db,
                mapping_id=mapping.id,
                action=AuditActionType.CORPORATE_ACTION_APPLY,
                old_value=old_value,
                new_value={
                    "ticker": mapping.ticker,
                    "version": mapping.version,
                    "corporate_action_id": action.id,
                },
                notes=f"Applied corporate action: {action.description}",
                request=request,
            )
            updated_count += 1

        action.is_processed = True
        action.processed_at = datetime.utcnow()
        action.status = CorporateActionStatus.APPLIED

        await db.commit()

        return {
            "status": "approved_and_applied",
            "corporate_action_id": action_id,
            "mappings_updated": updated_count,
        }

    elif decision.action == "reject":
        action.status = CorporateActionStatus.REJECTED
        action.rejection_reason = decision.notes
        await db.commit()

        return {
            "status": "rejected",
            "corporate_action_id": action_id,
            "reason": decision.notes,
        }

"""Admin API routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.entity_mappings import EntityMapping, MappingSuggestion, MappingStatus, SuggestionStatus
from src.models.data_sources import DataSource

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

    collector_name: str
    status: str  # up, down, degraded
    last_success: Optional[datetime]
    last_error: Optional[str]
    freshness_hours: float
    sla_hours: float
    sla_breach: bool


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
    """Get health status of all data collectors."""
    query = select(DataSource).where(DataSource.is_active == True)
    result = await db.execute(query)
    sources = result.scalars().all()

    # TODO: Get actual collector health from monitoring system
    return [
        CollectorHealthResponse(
            collector_name=s.name,
            status="up",  # TODO: Get actual status
            last_success=datetime.utcnow(),  # TODO: Get actual timestamp
            last_error=None,
            freshness_hours=s.latency_hours,
            sla_hours=s.latency_hours * 2,
            sla_breach=False,
        )
        for s in sources
    ]


@router.post("/collectors/{source_id}/trigger")
async def trigger_collector(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a collector run."""
    query = select(DataSource).where(DataSource.id == source_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found",
        )

    # TODO: Trigger actual collector via Celery
    return {
        "status": "triggered",
        "source_id": source_id,
        "source_name": source.name,
        "task_id": "placeholder-task-id",
    }


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

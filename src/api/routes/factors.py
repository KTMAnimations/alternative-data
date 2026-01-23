"""Factor API routes."""

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.factors import Factor, FactorValue, FactorRelationship, FactorDomain

router = APIRouter()


# Pydantic schemas
class FactorResponse(BaseModel):
    """Response schema for factor."""

    id: int
    factor_id: str
    name: str
    description: str
    domain: FactorDomain
    formula: str
    formula_description: str
    economic_rationale: str
    primary_entities: list[str]
    historical_ic: Optional[float]
    historical_ir: Optional[float]
    historical_tstat: Optional[float]
    historical_hit_rate: Optional[float]
    is_active: bool

    class Config:
        from_attributes = True


class FactorDetailResponse(FactorResponse):
    """Detailed factor response with full documentation."""

    literature_references: list[dict]
    signal_interpretation: str
    known_limitations: Optional[str]
    secondary_entities: list[str]
    decay_1d: Optional[float]
    decay_5d: Optional[float]
    decay_10d: Optional[float]
    decay_21d: Optional[float]
    decay_63d: Optional[float]
    estimated_half_life_days: Optional[int]


class FactorValueResponse(BaseModel):
    """Response schema for factor value."""

    ticker: str
    factor_id: str
    as_of_date: date
    mean: float
    variance: float
    data_quality: float
    revision_status: str

    class Config:
        from_attributes = True


class FactorHistoryResponse(BaseModel):
    """Response for factor history query."""

    factor_id: str
    data: list[FactorValueResponse]
    total_count: int
    cursor: Optional[str]


class GraphNode(BaseModel):
    """Node in factor graph."""

    id: str
    name: str
    domain: FactorDomain
    metrics: dict


class GraphEdge(BaseModel):
    """Edge in factor graph."""

    source: str
    target: str
    relationship_type: str
    strength: Optional[float]


class FactorGraphResponse(BaseModel):
    """Response for factor graph."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class CompareRequest(BaseModel):
    """Request for factor comparison."""

    factor_ids: list[str] = Field(..., min_length=2, max_length=4)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class BlendRequest(BaseModel):
    """Request for factor blending."""

    factor_ids: list[str] = Field(..., min_length=2)
    objective: str = Field(default="max_ic", pattern="^(max_ic|max_sharpe|min_correlation|multi_objective)$")
    constraints: dict = Field(default_factory=dict)


# Routes
@router.get("", response_model=list[FactorResponse])
async def list_factors(
    domain: Optional[FactorDomain] = None,
    search: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List all factors with optional filtering."""
    query = select(Factor)

    if active_only:
        query = query.where(Factor.is_active == True)
    if domain:
        query = query.where(Factor.domain == domain)
    if search:
        search_term = f"%{search}%"
        query = query.where(Factor.name.ilike(search_term))

    result = await db.execute(query)
    factors = result.scalars().all()

    return [FactorResponse.model_validate(f) for f in factors]


@router.get("/graph", response_model=FactorGraphResponse)
async def get_factor_graph(
    domain: Optional[FactorDomain] = None,
    relationship_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get factor relationship graph for visualization."""
    # Get factors
    factor_query = select(Factor).where(Factor.is_active == True)
    if domain:
        factor_query = factor_query.where(Factor.domain == domain)

    factor_result = await db.execute(factor_query)
    factors = factor_result.scalars().all()

    nodes = [
        GraphNode(
            id=f.factor_id,
            name=f.name,
            domain=f.domain,
            metrics={
                "ic": float(f.historical_ic) if f.historical_ic else None,
                "ir": float(f.historical_ir) if f.historical_ir else None,
            },
        )
        for f in factors
    ]

    # Get relationships
    rel_query = select(FactorRelationship)
    if relationship_type:
        rel_query = rel_query.where(FactorRelationship.relationship_type == relationship_type)

    rel_result = await db.execute(rel_query)
    relationships = rel_result.scalars().all()

    # Map factor IDs
    factor_id_map = {f.id: f.factor_id for f in factors}

    edges = [
        GraphEdge(
            source=factor_id_map.get(r.source_factor_id, str(r.source_factor_id)),
            target=factor_id_map.get(r.target_factor_id, str(r.target_factor_id)),
            relationship_type=r.relationship_type.value,
            strength=float(r.strength) if r.strength else None,
        )
        for r in relationships
        if r.source_factor_id in factor_id_map and r.target_factor_id in factor_id_map
    ]

    return FactorGraphResponse(nodes=nodes, edges=edges)


@router.get("/{factor_id}", response_model=FactorDetailResponse)
async def get_factor(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed documentation for a factor."""
    query = select(Factor).where(Factor.factor_id == factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    return FactorDetailResponse.model_validate(factor)


@router.get("/{factor_id}/history", response_model=FactorHistoryResponse)
async def get_factor_history(
    factor_id: str,
    tickers: str = Query(..., description="Comma-separated list of tickers"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    cursor: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Query historical factor values."""
    # Get factor
    factor_query = select(Factor).where(Factor.factor_id == factor_id)
    factor_result = await db.execute(factor_query)
    factor = factor_result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    # Parse tickers
    ticker_list = [t.strip().upper() for t in tickers.split(",")]

    # Build query
    query = (
        select(FactorValue)
        .where(FactorValue.factor_id == factor.id)
        .where(FactorValue.ticker.in_(ticker_list))
    )

    if start_date:
        query = query.where(FactorValue.as_of_date >= start_date)
    if end_date:
        query = query.where(FactorValue.as_of_date <= end_date)

    query = query.order_by(FactorValue.as_of_date.desc()).limit(limit + 1)

    result = await db.execute(query)
    values = result.scalars().all()

    # Handle pagination
    has_more = len(values) > limit
    if has_more:
        values = values[:limit]

    next_cursor = None
    if has_more and values:
        next_cursor = str(values[-1].id)

    return FactorHistoryResponse(
        factor_id=factor_id,
        data=[
            FactorValueResponse(
                ticker=v.ticker,
                factor_id=factor_id,
                as_of_date=v.as_of_date,
                mean=float(v.mean),
                variance=float(v.variance),
                data_quality=float(v.data_quality),
                revision_status=v.revision_status,
            )
            for v in values
        ],
        total_count=len(values),
        cursor=next_cursor,
    )


@router.get("/{factor_id}/decay")
async def get_factor_decay(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get factor decay analysis."""
    query = select(Factor).where(Factor.factor_id == factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    return {
        "factor_id": factor_id,
        "decay_curve": {
            "1d": float(factor.decay_1d) if factor.decay_1d else None,
            "5d": float(factor.decay_5d) if factor.decay_5d else None,
            "10d": float(factor.decay_10d) if factor.decay_10d else None,
            "21d": float(factor.decay_21d) if factor.decay_21d else None,
            "63d": float(factor.decay_63d) if factor.decay_63d else None,
        },
        "half_life_days": factor.estimated_half_life_days,
    }


@router.post("/compare")
async def compare_factors(
    request: CompareRequest,
    db: AsyncSession = Depends(get_db),
):
    """Compare multiple factors side-by-side."""
    # Get factors
    query = select(Factor).where(Factor.factor_id.in_(request.factor_ids))
    result = await db.execute(query)
    factors = result.scalars().all()

    if len(factors) != len(request.factor_ids):
        found = {f.factor_id for f in factors}
        missing = set(request.factor_ids) - found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factors not found: {missing}",
        )

    # Build comparison
    comparison = {
        "factors": [
            {
                "factor_id": f.factor_id,
                "name": f.name,
                "ic": float(f.historical_ic) if f.historical_ic else None,
                "ir": float(f.historical_ir) if f.historical_ir else None,
                "tstat": float(f.historical_tstat) if f.historical_tstat else None,
                "hit_rate": float(f.historical_hit_rate) if f.historical_hit_rate else None,
            }
            for f in factors
        ],
        "correlation_matrix": {},  # TODO: Compute from factor values
        "significance_flags": {},
    }

    return comparison


@router.post("/blend")
async def blend_factors(
    request: BlendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Blend multiple factors with optimization."""
    # Validate factors exist
    query = select(Factor).where(Factor.factor_id.in_(request.factor_ids))
    result = await db.execute(query)
    factors = result.scalars().all()

    if len(factors) != len(request.factor_ids):
        found = {f.factor_id for f in factors}
        missing = set(request.factor_ids) - found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factors not found: {missing}",
        )

    # TODO: Implement actual optimization
    # For now, return equal weights
    n = len(factors)
    weights = {f.factor_id: 1.0 / n for f in factors}

    return {
        "factor_ids": request.factor_ids,
        "objective": request.objective,
        "optimal_weights": weights,
        "blended_metrics": {
            "ic": None,  # TODO: Compute
            "ir": None,
            "tstat": None,
        },
    }

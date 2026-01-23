"""Data catalog API routes."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.data_sources import (
    DataSource,
    DataSourceCategory,
    UpdateFrequency,
    SaturationLevel,
)

router = APIRouter()


# Pydantic schemas
class DataSourceResponse(BaseModel):
    """Response schema for data source."""

    id: int
    name: str
    description: str
    category: DataSourceCategory
    update_frequency: UpdateFrequency
    latency_hours: float
    is_real_time: bool
    saturation_level: SaturationLevel
    primary_entities: list[str]
    geographic_coverage: Optional[str]
    date_range_start: Optional[date]
    date_range_end: Optional[date]
    is_active: bool
    is_archived: bool

    class Config:
        from_attributes = True


class DataSourceListResponse(BaseModel):
    """Response schema for data source list."""

    items: list[DataSourceResponse]
    total: int
    page: int
    page_size: int


class DataSourceDetailResponse(DataSourceResponse):
    """Detailed response with additional metadata."""

    api_documentation_url: Optional[str]
    archived_reason: Optional[str]
    sample_code: Optional[str] = None
    derived_factors: list[str] = []


class PreviewResponse(BaseModel):
    """Response for data preview."""

    source_id: int
    source_name: str
    data: list[dict]
    row_count: int
    completeness_pct: float
    last_updated: Optional[date]
    statistics: dict


# Routes
@router.get("/sources", response_model=DataSourceListResponse)
async def list_sources(
    category: Optional[DataSourceCategory] = None,
    frequency: Optional[UpdateFrequency] = None,
    search: Optional[str] = None,
    sort_by: str = Query("name", regex="^(name|saturation_level|latency_hours)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all data sources with filtering and pagination."""
    query = select(DataSource).where(DataSource.is_active == True)

    # Apply filters
    if category:
        query = query.where(DataSource.category == category)
    if frequency:
        query = query.where(DataSource.update_frequency == frequency)
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                DataSource.name.ilike(search_term),
                DataSource.description.ilike(search_term),
            )
        )

    # Count total
    count_query = select(DataSource.id).where(DataSource.is_active == True)
    if category:
        count_query = count_query.where(DataSource.category == category)
    if frequency:
        count_query = count_query.where(DataSource.update_frequency == frequency)
    if search:
        count_query = count_query.where(
            or_(
                DataSource.name.ilike(search_term),
                DataSource.description.ilike(search_term),
            )
        )

    # Sorting
    sort_column = getattr(DataSource, sort_by)
    if sort_order == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    sources = result.scalars().all()

    count_result = await db.execute(count_query)
    total = len(count_result.all())

    return DataSourceListResponse(
        items=[DataSourceResponse.model_validate(s) for s in sources],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sources/{source_id}", response_model=DataSourceDetailResponse)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed metadata for a specific data source."""
    query = select(DataSource).where(DataSource.id == source_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found",
        )

    # Add sample code and derived factors
    response = DataSourceDetailResponse.model_validate(source)
    response.sample_code = _generate_sample_code(source)
    response.derived_factors = await _get_derived_factors(db, source_id)

    return response


@router.get("/sources/{source_id}/preview", response_model=PreviewResponse)
async def preview_source_data(
    source_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    ticker: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Preview sample data from a source."""
    # Verify source exists
    query = select(DataSource).where(DataSource.id == source_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source {source_id} not found",
        )

    # Get preview data based on source type
    data, stats = await _get_preview_data(db, source, start_date, end_date, ticker, limit)

    return PreviewResponse(
        source_id=source_id,
        source_name=source.name,
        data=data,
        row_count=len(data),
        completeness_pct=stats.get("completeness", 100.0),
        last_updated=stats.get("last_updated"),
        statistics=stats,
    )


@router.post("/search/semantic")
async def semantic_search(
    query: str = Query(..., min_length=3),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Natural language search for data sources."""
    # TODO: Integrate LLM for semantic search
    # For now, use keyword search as fallback
    search_term = f"%{query}%"
    db_query = (
        select(DataSource)
        .where(DataSource.is_active == True)
        .where(
            or_(
                DataSource.name.ilike(search_term),
                DataSource.description.ilike(search_term),
            )
        )
        .limit(limit)
    )

    result = await db.execute(db_query)
    sources = result.scalars().all()

    return {
        "query": query,
        "results": [
            {
                "source": DataSourceResponse.model_validate(s),
                "relevance_score": 0.8,  # Placeholder
                "match_reason": f"Keyword match in {'name' if query.lower() in s.name.lower() else 'description'}",
            }
            for s in sources
        ],
        "related_sources": [],  # TODO: Implement
    }


# Helper functions
def _generate_sample_code(source: DataSource) -> str:
    """Generate sample API code for a data source."""
    return f'''from altdata import Client

client = Client(api_key="YOUR_API_KEY")

# Get latest data from {source.name}
data = client.sources.get("{source.name.lower().replace(" ", "_")}")
print(data.to_dataframe())
'''


async def _get_derived_factors(db: AsyncSession, source_id: int) -> list[str]:
    """Get list of factors derived from this source."""
    from src.models.factors import Factor

    query = select(Factor.factor_id).where(Factor.source_id == source_id)
    result = await db.execute(query)
    return [r[0] for r in result.all()]


async def _get_preview_data(
    db: AsyncSession,
    source: DataSource,
    start_date: Optional[date],
    end_date: Optional[date],
    ticker: Optional[str],
    limit: int,
) -> tuple[list[dict], dict]:
    """Get preview data for a source."""
    # Map source to data table
    from src.models.data_sources import TSACheckpoint, OpenTableMetrics, EarthquakeEvent

    source_tables = {
        "TSA Checkpoint": TSACheckpoint,
        "OpenTable": OpenTableMetrics,
        "USGS Earthquake": EarthquakeEvent,
    }

    table = source_tables.get(source.name)
    if not table:
        return [], {"completeness": 100.0}

    query = select(table).limit(limit)

    if hasattr(table, "date") and start_date:
        query = query.where(table.date >= start_date)
    if hasattr(table, "date") and end_date:
        query = query.where(table.date <= end_date)

    result = await db.execute(query)
    records = result.scalars().all()

    data = [r.to_dict() for r in records]
    stats = {
        "completeness": 100.0,
        "last_updated": records[-1].created_at if records else None,
        "row_count": len(records),
    }

    return data, stats

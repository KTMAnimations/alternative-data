"""Geographic visualization API routes."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.data_sources import EarthquakeEvent

router = APIRouter()


# Pydantic schemas
class GeoPoint(BaseModel):
    """Geographic point."""

    latitude: float
    longitude: float


class EarthquakeFeature(BaseModel):
    """GeoJSON feature for earthquake."""

    type: str = "Feature"
    geometry: dict
    properties: dict


class EarthquakeGeoJSON(BaseModel):
    """GeoJSON response for earthquakes."""

    type: str = "FeatureCollection"
    features: list[EarthquakeFeature]


class EarthquakeDetail(BaseModel):
    """Detailed earthquake information."""

    event_id: str
    timestamp: datetime
    magnitude: float
    magnitude_type: str
    depth_km: float
    location: GeoPoint
    place_description: str
    felt_reports: Optional[int]
    tsunami_flag: bool
    estimated_population_exposure: Optional[int]
    estimated_economic_impact_usd: Optional[float]
    insurance_estimates: list[dict]


class RegionalThresholdConfig(BaseModel):
    """Configuration for regional magnitude thresholds."""

    region_name: str
    geometry: dict  # GeoJSON polygon
    magnitude_threshold: float = Field(..., ge=0, le=10)


class PowerGridNode(BaseModel):
    """Power grid node with LMP data."""

    node_id: str
    iso_region: str
    location: GeoPoint
    current_lmp: float
    lmp_percentile: float
    renewable_share: Optional[float]


# Routes
@router.get("/earthquakes", response_model=EarthquakeGeoJSON)
async def get_earthquakes(
    magnitude_min: float = Query(4.0, ge=0, le=10),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Get earthquake events as GeoJSON for map visualization."""
    query = select(EarthquakeEvent).where(EarthquakeEvent.magnitude >= magnitude_min)

    if start_date:
        query = query.where(EarthquakeEvent.timestamp >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.where(EarthquakeEvent.timestamp <= datetime.combine(end_date, datetime.max.time()))

    query = query.order_by(EarthquakeEvent.timestamp.desc()).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    features = [
        EarthquakeFeature(
            geometry={
                "type": "Point",
                "coordinates": [float(e.longitude), float(e.latitude)],
            },
            properties={
                "event_id": e.event_id,
                "magnitude": float(e.magnitude),
                "magnitude_type": e.magnitude_type,
                "depth_km": float(e.depth_km),
                "timestamp": e.timestamp.isoformat(),
                "place": e.place_description,
                "tsunami": e.tsunami_flag,
                "felt_reports": e.felt_reports,
            },
        )
        for e in events
    ]

    return EarthquakeGeoJSON(features=features)


@router.get("/earthquakes/{event_id}", response_model=EarthquakeDetail)
async def get_earthquake_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed earthquake information with impact estimates."""
    query = select(EarthquakeEvent).where(EarthquakeEvent.event_id == event_id)
    result = await db.execute(query)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Earthquake event {event_id} not found",
        )

    # Calculate insurance estimates (placeholder)
    insurance_estimates = _calculate_insurance_estimates(event)

    return EarthquakeDetail(
        event_id=event.event_id,
        timestamp=event.timestamp,
        magnitude=float(event.magnitude),
        magnitude_type=event.magnitude_type,
        depth_km=float(event.depth_km),
        location=GeoPoint(
            latitude=float(event.latitude),
            longitude=float(event.longitude),
        ),
        place_description=event.place_description,
        felt_reports=event.felt_reports,
        tsunami_flag=event.tsunami_flag,
        estimated_population_exposure=event.estimated_population_exposure,
        estimated_economic_impact_usd=float(event.estimated_economic_impact_usd) if event.estimated_economic_impact_usd else None,
        insurance_estimates=insurance_estimates,
    )


@router.get("/power-grid")
async def get_power_grid(
    iso_region: Optional[str] = Query(None, description="Filter by ISO region (PJM, ERCOT, etc.)"),
    price_percentile_min: Optional[float] = Query(None, ge=0, le=100),
    include_renewable_share: bool = True,
    timestamp: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get power grid LMP data for map visualization."""
    # TODO: Implement actual LMP data query
    # For now, return placeholder data

    iso_regions = ["PJM", "ERCOT", "CAISO", "ISO-NE", "MISO", "SPP", "NYISO"]

    if iso_region and iso_region not in iso_regions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ISO region. Must be one of: {iso_regions}",
        )

    # Placeholder response
    return {
        "timestamp": timestamp or datetime.utcnow(),
        "iso_regions": iso_regions if not iso_region else [iso_region],
        "nodes": [],  # TODO: Populate with actual data
        "heat_map_data": [],  # TODO: Generate heat map overlay data
    }


@router.get("/power-grid/history")
async def get_power_grid_history(
    node_id: str,
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db),
):
    """Get historical LMP prices for a specific node."""
    # TODO: Implement actual query
    return {
        "node_id": node_id,
        "start_date": start_date,
        "end_date": end_date,
        "data": [],
    }


@router.post("/thresholds/regional")
async def configure_regional_thresholds(
    config: RegionalThresholdConfig,
    db: AsyncSession = Depends(get_db),
    # TODO: Add admin auth
):
    """Configure magnitude thresholds by region."""
    # TODO: Store threshold configuration
    return {
        "status": "configured",
        "region_name": config.region_name,
        "magnitude_threshold": config.magnitude_threshold,
    }


@router.get("/thresholds/preview")
async def preview_threshold_events(
    magnitude_threshold: float = Query(..., ge=0, le=10),
    days_back: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Preview which events would trigger with given threshold."""
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=days_back)

    query = (
        select(EarthquakeEvent)
        .where(EarthquakeEvent.magnitude >= magnitude_threshold)
        .where(EarthquakeEvent.timestamp >= cutoff)
        .order_by(EarthquakeEvent.timestamp.desc())
    )

    result = await db.execute(query)
    events = result.scalars().all()

    return {
        "threshold": magnitude_threshold,
        "days_back": days_back,
        "event_count": len(events),
        "events": [
            {
                "event_id": e.event_id,
                "magnitude": float(e.magnitude),
                "timestamp": e.timestamp.isoformat(),
                "place": e.place_description,
            }
            for e in events[:20]  # Limit preview
        ],
    }


# Helper functions
def _calculate_insurance_estimates(event: EarthquakeEvent) -> list[dict]:
    """Calculate estimated insurance losses by insurer."""
    # Simplified model for demonstration
    # In production, this would use actual exposure data and loss models

    insurers = [
        {"ticker": "ALL", "name": "Allstate", "market_share": 0.15},
        {"ticker": "TRV", "name": "Travelers", "market_share": 0.12},
        {"ticker": "CB", "name": "Chubb", "market_share": 0.10},
        {"ticker": "PGR", "name": "Progressive", "market_share": 0.08},
    ]

    if not event.estimated_economic_impact_usd:
        return []

    total_insured_loss = float(event.estimated_economic_impact_usd) * 0.4  # 40% insured

    return [
        {
            "ticker": ins["ticker"],
            "name": ins["name"],
            "estimated_loss_mean": total_insured_loss * ins["market_share"],
            "estimated_loss_variance": (total_insured_loss * ins["market_share"] * 0.3) ** 2,
            "confidence_level": 0.7,
        }
        for ins in insurers
    ]

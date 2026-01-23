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


class RegionalExposure(BaseModel):
    """Regional exposure breakdown for insurance analysis."""

    region: str
    exposure_percentage: float = Field(..., ge=0, le=100)
    exposed_policies_estimate: Optional[int] = None
    exposure_value_usd: Optional[float] = None


class InsuranceEstimate(BaseModel):
    """Insurance loss estimate for a specific insurer."""

    ticker: str
    name: str
    estimated_loss_mean: float
    estimated_loss_variance: float
    confidence_level: float
    exposure_by_region: list[RegionalExposure] = Field(default_factory=list)
    reinsurance_percentage: float = Field(default=0.0, ge=0, le=100)
    net_retained_loss: Optional[float] = None


class HistoricalComparison(BaseModel):
    """Comparison to similar historical earthquake events."""

    event_id: str
    timestamp: datetime
    magnitude: float
    distance_km: float
    place_description: str
    actual_insured_loss_usd: Optional[float] = None
    similarity_score: float = Field(..., ge=0, le=1)


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
    insurance_estimates: list[InsuranceEstimate]
    historical_comparisons: list[HistoricalComparison] = Field(default_factory=list)


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
    include_historical: bool = Query(True, description="Include historical similar event comparisons"),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed earthquake information with impact estimates.

    Returns comprehensive earthquake data including:
    - Basic event information (magnitude, location, depth)
    - Estimated economic impact
    - Insurance loss estimates by major insurer with regional exposure breakdown
    - Reinsurance arrangements factored into net retained loss
    - Historical similar events for comparison (if include_historical=True)
    """
    query = select(EarthquakeEvent).where(EarthquakeEvent.event_id == event_id)
    result = await db.execute(query)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Earthquake event {event_id} not found",
        )

    # Find historical similar events for comparison
    historical_comparisons = []
    if include_historical:
        historical_comparisons = await _find_similar_historical_events(event, db)

    # Calculate insurance estimates with enhanced model
    insurance_estimates = _calculate_insurance_estimates(event, historical_comparisons)

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
        historical_comparisons=historical_comparisons,
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


# Insurance company configuration with regional exposure and reinsurance
INSURER_CONFIG = {
    "ALL": {
        "ticker": "ALL",
        "name": "Allstate",
        "market_share": 0.15,
        "reinsurance_percentage": 25.0,
        "regional_exposure": {
            "California": 0.35,
            "Pacific Northwest": 0.15,
            "Southwest": 0.20,
            "Midwest": 0.15,
            "Northeast": 0.10,
            "Southeast": 0.05,
        },
    },
    "TRV": {
        "ticker": "TRV",
        "name": "Travelers",
        "market_share": 0.12,
        "reinsurance_percentage": 30.0,
        "regional_exposure": {
            "California": 0.25,
            "Pacific Northwest": 0.10,
            "Southwest": 0.15,
            "Midwest": 0.20,
            "Northeast": 0.25,
            "Southeast": 0.05,
        },
    },
    "CB": {
        "ticker": "CB",
        "name": "Chubb",
        "market_share": 0.10,
        "reinsurance_percentage": 35.0,
        "regional_exposure": {
            "California": 0.40,
            "Pacific Northwest": 0.20,
            "Southwest": 0.10,
            "Midwest": 0.05,
            "Northeast": 0.15,
            "Southeast": 0.10,
        },
    },
    "PGR": {
        "ticker": "PGR",
        "name": "Progressive",
        "market_share": 0.08,
        "reinsurance_percentage": 20.0,
        "regional_exposure": {
            "California": 0.30,
            "Pacific Northwest": 0.15,
            "Southwest": 0.25,
            "Midwest": 0.15,
            "Northeast": 0.10,
            "Southeast": 0.05,
        },
    },
}


def _get_event_region(lat: float, lon: float) -> str:
    """Determine the region based on earthquake coordinates."""
    # California
    if lat >= 32 and lat <= 42 and lon >= -125 and lon <= -114:
        return "California"
    # Pacific Northwest
    if lat >= 42 and lat <= 49 and lon >= -125 and lon <= -116:
        return "Pacific Northwest"
    # Southwest (AZ, NM, NV)
    if lat >= 31 and lat <= 42 and lon >= -115 and lon <= -103:
        return "Southwest"
    # Hawaii
    if lat >= 18 and lat <= 23 and lon >= -161 and lon <= -154:
        return "Hawaii"
    # Alaska
    if lat >= 51 and lat <= 72 and lon >= -170 and lon <= -130:
        return "Alaska"
    # Default to other
    return "Other"


async def _find_similar_historical_events(
    event: EarthquakeEvent,
    db: AsyncSession,
    limit: int = 5,
) -> list[HistoricalComparison]:
    """Find historical events similar to the given event by magnitude and location."""
    from math import radians, sin, cos, sqrt, atan2

    # Query for events with similar magnitude (within 0.5) in the past
    magnitude_range = Decimal("0.5")
    min_mag = event.magnitude - magnitude_range
    max_mag = event.magnitude + magnitude_range

    query = (
        select(EarthquakeEvent)
        .where(EarthquakeEvent.event_id != event.event_id)
        .where(EarthquakeEvent.magnitude >= min_mag)
        .where(EarthquakeEvent.magnitude <= max_mag)
        .where(EarthquakeEvent.timestamp < event.timestamp)
        .order_by(EarthquakeEvent.timestamp.desc())
        .limit(50)  # Get more candidates for filtering
    )

    result = await db.execute(query)
    candidates = result.scalars().all()

    if not candidates:
        return []

    # Calculate distance and similarity score for each candidate
    event_lat = float(event.latitude)
    event_lon = float(event.longitude)
    event_mag = float(event.magnitude)

    comparisons = []
    for candidate in candidates:
        cand_lat = float(candidate.latitude)
        cand_lon = float(candidate.longitude)
        cand_mag = float(candidate.magnitude)

        # Haversine distance calculation
        R = 6371  # Earth radius in km
        lat1, lat2 = radians(event_lat), radians(cand_lat)
        dlat = radians(cand_lat - event_lat)
        dlon = radians(cand_lon - event_lon)

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance_km = R * c

        # Calculate similarity score (0-1)
        # Based on magnitude difference and distance
        mag_similarity = 1.0 - abs(event_mag - cand_mag) / 2.0  # 0-1 scale
        # Distance similarity: 1.0 at 0km, 0.0 at 1000km+
        dist_similarity = max(0.0, 1.0 - distance_km / 1000.0)

        # Combined similarity (weighted average)
        similarity_score = 0.6 * mag_similarity + 0.4 * dist_similarity

        # Only include events within 1000km and similarity > 0.3
        if distance_km <= 1000 and similarity_score > 0.3:
            comparisons.append(HistoricalComparison(
                event_id=candidate.event_id,
                timestamp=candidate.timestamp,
                magnitude=float(candidate.magnitude),
                distance_km=round(distance_km, 2),
                place_description=candidate.place_description,
                actual_insured_loss_usd=float(candidate.estimated_economic_impact_usd * Decimal("0.4"))
                    if candidate.estimated_economic_impact_usd else None,
                similarity_score=round(similarity_score, 3),
            ))

    # Sort by similarity and return top N
    comparisons.sort(key=lambda x: x.similarity_score, reverse=True)
    return comparisons[:limit]


def _calculate_insurance_estimates(
    event: EarthquakeEvent,
    historical_comparisons: list[HistoricalComparison] = None,
) -> list[InsuranceEstimate]:
    """Calculate estimated insurance losses by insurer with enhanced model.

    This enhanced model factors in:
    - Geographic book exposure by region
    - Reinsurance arrangements
    - Historical similar event data for calibration
    """
    if not event.estimated_economic_impact_usd:
        return []

    # Determine affected region
    affected_region = _get_event_region(float(event.latitude), float(event.longitude))

    # Base insured loss (40% of economic damage typically insured)
    base_insured_pct = 0.40

    # Adjust based on historical comparisons if available
    historical_multiplier = 1.0
    if historical_comparisons:
        actual_losses = [h.actual_insured_loss_usd for h in historical_comparisons if h.actual_insured_loss_usd]
        if actual_losses:
            avg_historical_loss = sum(actual_losses) / len(actual_losses)
            expected_loss = float(event.estimated_economic_impact_usd) * base_insured_pct
            if expected_loss > 0:
                # Adjust multiplier based on historical data (bounded)
                historical_multiplier = min(max(avg_historical_loss / expected_loss, 0.5), 2.0)

    total_insured_loss = float(event.estimated_economic_impact_usd) * base_insured_pct * historical_multiplier

    estimates = []
    for ticker, config in INSURER_CONFIG.items():
        # Get regional exposure factor for affected region
        regional_exposure = config["regional_exposure"].get(affected_region, 0.05)

        # Calculate gross loss (market share weighted by regional exposure)
        gross_loss = total_insured_loss * config["market_share"] * regional_exposure * 10  # Scale by regional factor

        # Apply reinsurance to get net retained loss
        reinsurance_pct = config["reinsurance_percentage"]
        net_retained_loss = gross_loss * (1 - reinsurance_pct / 100)

        # Variance increases with magnitude uncertainty
        magnitude_uncertainty = max(0.2, (float(event.magnitude) - 5.0) * 0.1)
        variance = (gross_loss * (0.3 + magnitude_uncertainty)) ** 2

        # Build regional exposure breakdown
        exposure_by_region = []
        for region, exposure_pct in config["regional_exposure"].items():
            exposure_by_region.append(RegionalExposure(
                region=region,
                exposure_percentage=round(exposure_pct * 100, 1),
                exposure_value_usd=round(total_insured_loss * config["market_share"] * exposure_pct, 2)
                    if total_insured_loss > 0 else None,
            ))

        estimates.append(InsuranceEstimate(
            ticker=config["ticker"],
            name=config["name"],
            estimated_loss_mean=round(gross_loss, 2),
            estimated_loss_variance=round(variance, 2),
            confidence_level=0.7 + (0.1 if historical_comparisons else 0.0),
            exposure_by_region=exposure_by_region,
            reinsurance_percentage=reinsurance_pct,
            net_retained_loss=round(net_retained_loss, 2),
        ))

    return estimates

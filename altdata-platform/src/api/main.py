"""FastAPI application for the Alternative Data Platform."""

from datetime import datetime, timedelta, date
from typing import List, Optional

import redis
from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.config.settings import settings
from src.models.database import get_db, check_database_connection, SessionLocal
from src.models.schemas import Entity, Factor, FactorDefinition
from src.models.adsb import Aircraft, FlightLanding
from src.models.power_grid import GridLoad, GenerationMix
from src.models.patents import Patent, PatentAssignee
from src.models.air_quality import AirQualityMeasurement, AirQualityLocation
from src.models.weather import WeatherObservation, WeatherForecast, WeatherDaily
from src.models.trends import TrendInterest, TrendKeyword
from src.models.sentiment import RedditPost, TickerMention, TickerSentimentDaily
from src.models.shipping import Port, PortCongestion, Vessel, VesselPosition, GlobalShippingIndex
from src.models.github import GitHubRepository, GitHubRepoMetrics, GitHubCommit
from src.models.satellite import SatelliteLocation, ParkingLotMetrics, AgriculturalMetrics, PortActivityMetrics
from src.transformations.base import FactorRegistry

# Import factors to register them
from src.transformations.factors import (
    # SEC factors
    InsiderTransactionMomentum,
    InsiderClusteringScore,
    EventVelocity8K,
    # Macro factors
    YieldCurveSlope,
    CreditSpreadIndex,
    # Aviation factors
    ExecutiveFlightFrequency,
    HQVisitScore,
    UnusualDestinationAlert,
    MultiCompanyColocation,
    # Power grid factors
    GridLoadSurprise,
    RegionalPowerDemand,
    RenewableShare,
    LoadCapacityRatio,
    YoYDemandChange,
    # Patent factors
    PatentMomentum,
    InnovationVelocity,
    PatentQualityScore,
    TechnologyDiversity,
    TimeToGrant,
    # Air quality factors
    AirQualityAnomaly,
    IndustrialActivityProxy,
    PollutionTrend,
    RegionalAQI,
    # Phase 2 - Weather factors
    HeatingDegreeDays,
    CoolingDegreeDays,
    RetailWeatherIndex,
    AgriculturalStressIndex,
    WeatherYoYAnomaly,
    PrecipitationAnomaly,
    # Phase 2 - Trends factors
    SearchMomentum,
    SearchVolatility,
    SearchYoYChange,
    CategoryInterest,
    RetailSentimentIndex,
    # Phase 2 - Sentiment factors
    TickerSentiment,
    MentionVelocity,
    SentimentMomentum,
    WSBSentiment,
    RetailAttentionIndex,
    SentimentDispersion,
    # Phase 2 - Shipping factors
    PortCongestionIndex,
    PortActivityChange,
    ContainerVesselCount,
    TankerActivityIndex,
    GlobalCongestionIndex,
    ChinaUSTradeFlow,
    # Phase 2 - GitHub factors
    DeveloperVelocity,
    CommitMomentum,
    ReleaseFrequency,
    StarGrowthRate,
    ContributorDiversity,
    TechSectorActivity,
    # Phase 2 - Satellite factors
    ParkingOccupancy,
    ParkingTrend,
    ConstructionProgress,
    CropHealthIndex,
    NDVIAnomaly,
    RetailTrafficProxy,
)

# ===========================================
# APPLICATION SETUP
# ===========================================

app = FastAPI(
    title="Alternative Data Platform API",
    description="Access alternative data factors for quantitative trading",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis cache
_redis_client = None


def get_redis():
    """Get Redis client (lazy initialization)."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(settings.redis_url)
            _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client


# ===========================================
# SCHEMAS
# ===========================================

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    database: str
    redis: str
    version: str


class FactorValue(BaseModel):
    date: datetime
    value: Optional[float]
    version: int = 1


class FactorResponse(BaseModel):
    factor_name: str
    entity_id: str
    entity_type: str
    values: List[FactorValue]
    metadata: dict = Field(default_factory=dict)


class FactorListItem(BaseModel):
    id: str
    name: str
    description: Optional[str]
    category: str
    frequency: str


class FactorListResponse(BaseModel):
    factors: List[FactorListItem]
    total: int


class EntityResponse(BaseModel):
    id: str
    name: str
    ticker: Optional[str]
    entity_type: str
    sector: Optional[str]
    industry: Optional[str]


class EntityListResponse(BaseModel):
    entities: List[EntityResponse]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


# Phase 1 Stage 6 Schemas
class FlightRecord(BaseModel):
    icao_hex: str
    registration: Optional[str]
    landing_timestamp: datetime
    airport_icao: Optional[str]
    airport_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    nearest_company_hq: Optional[str]
    distance_to_hq_km: Optional[float]


class FlightListResponse(BaseModel):
    company_id: str
    flights: List[FlightRecord]
    total: int


class GridLoadRecord(BaseModel):
    iso_region: str
    timestamp: datetime
    load_mw: Optional[float]
    forecast_mw: Optional[float]
    capacity_mw: Optional[float]
    load_pct_of_capacity: Optional[float]


class GridLoadResponse(BaseModel):
    iso: str
    date: date
    readings: List[GridLoadRecord]
    total: int


class PatentRecord(BaseModel):
    patent_number: str
    application_number: Optional[str]
    title: Optional[str]
    filing_date: Optional[date]
    grant_date: Optional[date]
    status: Optional[str]
    primary_class: Optional[str]
    claims_count: Optional[int]


class PatentListResponse(BaseModel):
    company_id: str
    patents: List[PatentRecord]
    total: int


class AirQualityRecord(BaseModel):
    location_id: Optional[str]
    location_name: Optional[str]
    city: Optional[str]
    country: Optional[str]
    timestamp: datetime
    parameter: str
    value: Optional[float]
    unit: Optional[str]
    aqi: Optional[int]


class AirQualityResponse(BaseModel):
    city: Optional[str]
    country: Optional[str]
    date: date
    readings: List[AirQualityRecord]
    total: int


# ===========================================
# PHASE 2 SCHEMAS
# ===========================================

class WeatherRecord(BaseModel):
    city: str
    timestamp: datetime
    temp_c: Optional[float]
    temp_feels_like_c: Optional[float]
    humidity_pct: Optional[int]
    wind_speed_ms: Optional[float]
    weather_main: Optional[str]
    pressure_hpa: Optional[int]


class WeatherResponse(BaseModel):
    city: str
    date: date
    observations: List[WeatherRecord]
    total: int


class WeatherForecastRecord(BaseModel):
    city: str
    forecast_timestamp: datetime
    temp_c: Optional[float]
    humidity_pct: Optional[int]
    wind_speed_ms: Optional[float]
    weather_main: Optional[str]
    pop: Optional[float]  # Probability of precipitation


class WeatherForecastResponse(BaseModel):
    city: str
    forecasts: List[WeatherForecastRecord]
    total: int


class TrendRecord(BaseModel):
    keyword: str
    date: date
    interest: Optional[int]
    is_partial: bool = False
    geo: Optional[str]


class TrendResponse(BaseModel):
    keyword: str
    geo: Optional[str]
    data: List[TrendRecord]
    total: int


class SentimentRecord(BaseModel):
    ticker: str
    date: date
    avg_sentiment: Optional[float]
    mention_count: Optional[int]
    positive_mentions: Optional[int]
    negative_mentions: Optional[int]
    neutral_mentions: Optional[int]


class SentimentResponse(BaseModel):
    ticker: str
    data: List[SentimentRecord]
    total: int


class PortRecord(BaseModel):
    port_id: str
    port_name: str
    country: str
    latitude: Optional[float]
    longitude: Optional[float]
    port_type: Optional[str]


class PortListResponse(BaseModel):
    ports: List[PortRecord]
    total: int


class CongestionRecord(BaseModel):
    port_id: str
    port_name: Optional[str]
    date: date
    congestion_index: Optional[float]
    vessels_waiting: Optional[int]
    avg_wait_hours: Optional[float]


class CongestionResponse(BaseModel):
    port_id: Optional[str]
    date: date
    data: List[CongestionRecord]
    total: int


class GitHubRepoRecord(BaseModel):
    full_name: str
    company: Optional[str]
    ticker: Optional[str]
    stars: Optional[int]
    forks: Optional[int]
    open_issues: Optional[int]
    language: Optional[str]


class GitHubRepoListResponse(BaseModel):
    repos: List[GitHubRepoRecord]
    total: int


class GitHubActivityRecord(BaseModel):
    full_name: str
    date: date
    commits_24h: Optional[int]
    prs_opened_24h: Optional[int]
    prs_merged_24h: Optional[int]
    issues_opened_24h: Optional[int]
    unique_committers_24h: Optional[int]


class GitHubActivityResponse(BaseModel):
    repo: str
    data: List[GitHubActivityRecord]
    total: int


class ParkingRecord(BaseModel):
    location_id: str
    location_name: Optional[str]
    ticker: Optional[str]
    date: date
    occupancy_rate: Optional[float]
    cars_detected: Optional[int]
    confidence_score: Optional[float]


class ParkingResponse(BaseModel):
    ticker: Optional[str]
    data: List[ParkingRecord]
    total: int


class AgriculturalRecord(BaseModel):
    location_id: str
    region: str
    crop_type: Optional[str]
    date: date
    ndvi_mean: Optional[float]
    crop_health_score: Optional[float]
    ndvi_vs_historical: Optional[float]


class AgriculturalResponse(BaseModel):
    region: str
    crop_type: Optional[str]
    data: List[AgriculturalRecord]
    total: int


# ===========================================
# AUTHENTICATION
# ===========================================

async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """Verify API key from header.

    In production, this would check against the database.
    For MVP, we use simple environment variable check.
    """
    if settings.is_development and not x_api_key:
        return "development"

    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Pass via X-API-Key header."
        )

    # Check against configured keys
    valid_keys = [settings.api_key_admin, settings.api_key_default]
    if x_api_key not in valid_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return x_api_key


# ===========================================
# ROUTES
# ===========================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check system health status."""
    db_status = "connected" if check_database_connection() else "disconnected"

    redis_status = "disconnected"
    redis_client = get_redis()
    if redis_client:
        try:
            redis_client.ping()
            redis_status = "connected"
        except Exception:
            redis_status = "disconnected"

    status = "healthy"
    if db_status != "connected":
        status = "degraded"

    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        database=db_status,
        redis=redis_status,
        version="1.0.0",
    )


@app.get("/api/v1/factors", response_model=FactorListResponse, tags=["Factors"])
async def list_factors(
    category: Optional[str] = Query(None, description="Filter by category"),
    api_key: str = Depends(verify_api_key),
):
    """List all available factors."""
    # Get factors from registry
    all_factors = FactorRegistry.list_factors()

    factors = [
        FactorListItem(
            id=f["id"],
            name=f["id"].replace("_", " ").title(),
            description=f.get("description"),
            category=f["category"],
            frequency=f["frequency"],
        )
        for f in all_factors
    ]

    if category:
        factors = [f for f in factors if f.category == category]

    return FactorListResponse(factors=factors, total=len(factors))


@app.get(
    "/api/v1/factors/{factor_name}",
    response_model=FactorResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["Factors"],
)
async def get_factor(
    factor_name: str,
    entity_id: str = Query(..., description="Entity identifier (e.g., AAPL)"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    api_key: str = Depends(verify_api_key),
):
    """Get factor values for an entity."""
    # Check if factor exists in registry
    factor_class = FactorRegistry.get(factor_name)
    if not factor_class:
        raise HTTPException(status_code=404, detail=f"Factor '{factor_name}' not found")

    # Set default date range
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Query factors from database
    session = SessionLocal()
    try:
        query = (
            session.query(Factor)
            .filter(
                Factor.factor_name == factor_name,
                Factor.entity_id == entity_id,
                Factor.effective_date >= start_date,
                Factor.effective_date <= end_date,
            )
            .order_by(Factor.effective_date.desc())
        )

        results = query.all()

        values = [
            FactorValue(
                date=r.effective_date,
                value=r.value,
                version=r.version,
            )
            for r in results
        ]

        # If no stored values, compute current value
        if not values:
            factor_instance = factor_class()
            current_value = factor_instance.compute(entity_id, as_of_date=end_date)
            if current_value is not None:
                values = [
                    FactorValue(
                        date=end_date,
                        value=current_value,
                        version=1,
                    )
                ]

        entity_type = "company"
        if results:
            entity_type = results[0].entity_type
        else:
            factor_instance = factor_class()
            entity_type = factor_instance.ENTITY_TYPE

        return FactorResponse(
            factor_name=factor_name,
            entity_id=entity_id,
            entity_type=entity_type,
            values=values,
            metadata={
                "computed_at": datetime.utcnow().isoformat(),
                "data_freshness": end_date.isoformat() if results else None,
            }
        )
    finally:
        session.close()


@app.get("/api/v1/entities", response_model=EntityListResponse, tags=["Entities"])
async def list_entities(
    search: Optional[str] = Query(None, description="Search by name or ticker"),
    entity_type: Optional[str] = Query(None, description="Filter by type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    api_key: str = Depends(verify_api_key),
):
    """List and search entities."""
    session = SessionLocal()
    try:
        query = session.query(Entity)

        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Entity.name.ilike(search_pattern)) |
                (Entity.ticker.ilike(search_pattern))
            )

        total = query.count()

        # Pagination
        offset = (page - 1) * page_size
        results = query.offset(offset).limit(page_size).all()

        entities = [
            EntityResponse(
                id=e.id,
                name=e.name,
                ticker=e.ticker,
                entity_type=e.entity_type,
                sector=e.sector,
                industry=e.industry,
            )
            for e in results
        ]

        return EntityListResponse(
            entities=entities,
            total=total,
            page=page,
            page_size=page_size,
        )
    finally:
        session.close()


@app.get(
    "/api/v1/entities/{entity_id}",
    response_model=EntityResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["Entities"],
)
async def get_entity(
    entity_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Get entity details by ID."""
    session = SessionLocal()
    try:
        entity = session.query(Entity).filter_by(id=entity_id).first()

        if not entity:
            # Also try by ticker
            entity = session.query(Entity).filter_by(ticker=entity_id).first()

        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

        return EntityResponse(
            id=entity.id,
            name=entity.name,
            ticker=entity.ticker,
            entity_type=entity.entity_type,
            sector=entity.sector,
            industry=entity.industry,
        )
    finally:
        session.close()


@app.get("/api/v1/sources", tags=["Sources"])
async def list_sources(api_key: str = Depends(verify_api_key)):
    """List available data sources."""
    return {
        "sources": [
            {
                "id": "sec_edgar",
                "name": "SEC EDGAR",
                "category": "regulatory",
                "status": "active",
                "update_frequency": "real-time",
                "factors": ["insider_transaction_momentum", "insider_clustering_score", "8k_event_velocity"],
            },
            {
                "id": "fred",
                "name": "FRED",
                "category": "macroeconomic",
                "status": "active",
                "update_frequency": "daily",
                "factors": ["yield_curve_slope", "credit_spread_index", "financial_conditions_index"],
            },
            {
                "id": "adsb_exchange",
                "name": "ADS-B Exchange",
                "category": "aviation",
                "status": "active",
                "update_frequency": "real-time",
                "factors": ["executive_flight_frequency", "hq_visit_score", "unusual_destination_alert", "multi_company_colocation"],
            },
            {
                "id": "power_grid",
                "name": "US Power Grid ISOs",
                "category": "industrial",
                "status": "active",
                "update_frequency": "hourly",
                "factors": ["grid_load_surprise", "regional_power_demand", "renewable_share", "load_capacity_ratio"],
            },
            {
                "id": "uspto",
                "name": "USPTO Patents",
                "category": "innovation",
                "status": "active",
                "update_frequency": "daily",
                "factors": ["patent_momentum", "innovation_velocity", "patent_quality_score", "technology_diversity"],
            },
            {
                "id": "openaq",
                "name": "OpenAQ",
                "category": "environmental",
                "status": "active",
                "update_frequency": "hourly",
                "factors": ["air_quality_anomaly", "industrial_activity_proxy", "pollution_trend", "regional_aqi"],
            },
            # Phase 2 Sources
            {
                "id": "openweathermap",
                "name": "OpenWeatherMap",
                "category": "weather",
                "status": "active",
                "update_frequency": "hourly",
                "factors": ["heating_degree_days", "cooling_degree_days", "retail_weather_index", "agricultural_stress_index", "weather_yoy_anomaly", "precipitation_anomaly"],
            },
            {
                "id": "google_trends",
                "name": "Google Trends",
                "category": "consumer_interest",
                "status": "active",
                "update_frequency": "daily",
                "factors": ["search_momentum", "search_volatility", "search_yoy_change", "category_interest", "retail_sentiment_index"],
            },
            {
                "id": "reddit",
                "name": "Reddit Sentiment",
                "category": "social_sentiment",
                "status": "active",
                "update_frequency": "hourly",
                "factors": ["ticker_sentiment", "mention_velocity", "sentiment_momentum", "wsb_sentiment", "retail_attention_index", "sentiment_dispersion"],
            },
            {
                "id": "marine_traffic",
                "name": "MarineTraffic/AIS",
                "category": "shipping",
                "status": "active",
                "update_frequency": "hourly",
                "factors": ["port_congestion_index", "port_activity_change", "container_vessel_count", "tanker_activity_index", "global_congestion_index", "china_us_trade_flow"],
            },
            {
                "id": "github",
                "name": "GitHub Activity",
                "category": "developer_activity",
                "status": "active",
                "update_frequency": "daily",
                "factors": ["developer_velocity", "commit_momentum", "release_frequency", "star_growth_rate", "contributor_diversity", "tech_sector_activity"],
            },
            {
                "id": "sentinel",
                "name": "Sentinel-2 Satellite",
                "category": "satellite_imagery",
                "status": "active",
                "update_frequency": "weekly",
                "factors": ["parking_occupancy", "parking_trend", "construction_progress", "crop_health_index", "ndvi_anomaly", "retail_traffic_proxy"],
            },
        ]
    }


@app.get("/api/v1/categories", tags=["Factors"])
async def list_categories(api_key: str = Depends(verify_api_key)):
    """List all factor categories."""
    all_factors = FactorRegistry.list_factors()
    categories = {}

    for f in all_factors:
        cat = f["category"]
        if cat not in categories:
            categories[cat] = {"name": cat.replace("_", " ").title(), "count": 0, "factors": []}
        categories[cat]["count"] += 1
        categories[cat]["factors"].append(f["id"])

    return {
        "categories": [
            {"id": k, **v} for k, v in sorted(categories.items())
        ]
    }


# ===========================================
# PHASE 1 STAGE 6 ENDPOINTS
# ===========================================

@app.get("/api/v1/aviation/flights", response_model=FlightListResponse, tags=["Aviation"])
async def get_corporate_flights(
    company_id: str = Query(..., description="Company entity ID"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    api_key: str = Depends(verify_api_key),
):
    """Get corporate jet flight history for a company."""
    session = SessionLocal()
    try:
        # Default date range
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Query flights for company's aircraft
        query = (
            session.query(FlightLanding)
            .join(Aircraft, FlightLanding.aircraft_id == Aircraft.id)
            .filter(
                Aircraft.company_entity_id == company_id,
                func.date(FlightLanding.landing_timestamp) >= start_date,
                func.date(FlightLanding.landing_timestamp) <= end_date,
            )
            .order_by(FlightLanding.landing_timestamp.desc())
        )

        results = query.all()

        flights = [
            FlightRecord(
                icao_hex=f.icao_hex,
                registration=f.aircraft.registration if f.aircraft else None,
                landing_timestamp=f.landing_timestamp,
                airport_icao=f.airport_icao,
                airport_name=f.airport_name,
                latitude=f.latitude,
                longitude=f.longitude,
                nearest_company_hq=f.nearest_company_hq,
                distance_to_hq_km=f.distance_to_hq_km,
            )
            for f in results
        ]

        return FlightListResponse(
            company_id=company_id,
            flights=flights,
            total=len(flights),
        )
    finally:
        session.close()


@app.get("/api/v1/energy/load", response_model=GridLoadResponse, tags=["Energy"])
async def get_grid_load(
    iso: str = Query(..., description="ISO region", enum=["CAISO", "ERCOT", "PJM", "MISO"]),
    query_date: date = Query(..., alias="date", description="Date to query"),
    api_key: str = Depends(verify_api_key),
):
    """Get electricity load data for an ISO region."""
    session = SessionLocal()
    try:
        # Query grid load for the specified date
        query = (
            session.query(GridLoad)
            .filter(
                GridLoad.iso_region == iso,
                func.date(GridLoad.timestamp) == query_date,
            )
            .order_by(GridLoad.timestamp)
        )

        results = query.all()

        readings = [
            GridLoadRecord(
                iso_region=r.iso_region,
                timestamp=r.timestamp,
                load_mw=r.load_mw,
                forecast_mw=r.forecast_mw,
                capacity_mw=r.capacity_mw,
                load_pct_of_capacity=r.load_pct_of_capacity,
            )
            for r in results
        ]

        return GridLoadResponse(
            iso=iso,
            date=query_date,
            readings=readings,
            total=len(readings),
        )
    finally:
        session.close()


@app.get("/api/v1/patents/filings", response_model=PatentListResponse, tags=["Patents"])
async def get_patent_filings(
    company_id: str = Query(..., description="Company entity ID"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    api_key: str = Depends(verify_api_key),
):
    """Get patent filing history for a company."""
    session = SessionLocal()
    try:
        # Default date range
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=365)  # Last year by default

        # Query patents for company
        query = (
            session.query(Patent)
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == company_id,
            )
        )

        # Filter by grant date or filing date
        query = query.filter(
            ((Patent.grant_date >= start_date) & (Patent.grant_date <= end_date)) |
            ((Patent.filing_date >= start_date) & (Patent.filing_date <= end_date))
        )

        query = query.order_by(Patent.grant_date.desc().nullslast())

        results = query.all()

        patents = [
            PatentRecord(
                patent_number=p.patent_number,
                application_number=p.application_number,
                title=p.title,
                filing_date=p.filing_date,
                grant_date=p.grant_date,
                status=p.status,
                primary_class=p.primary_class,
                claims_count=p.claims_count,
            )
            for p in results
        ]

        return PatentListResponse(
            company_id=company_id,
            patents=patents,
            total=len(patents),
        )
    finally:
        session.close()


@app.get("/api/v1/environment/air-quality", response_model=AirQualityResponse, tags=["Environment"])
async def get_air_quality(
    query_date: date = Query(..., alias="date", description="Date to query"),
    city: Optional[str] = Query(None, description="Filter by city"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    parameter: Optional[str] = Query("pm25", description="Pollutant parameter"),
    api_key: str = Depends(verify_api_key),
):
    """Get air quality readings."""
    session = SessionLocal()
    try:
        # Build query
        query = (
            session.query(AirQualityMeasurement)
            .join(AirQualityLocation, AirQualityMeasurement.location_id == AirQualityLocation.location_id)
            .filter(
                func.date(AirQualityMeasurement.timestamp) == query_date,
            )
        )

        if city:
            query = query.filter(AirQualityLocation.city.ilike(f"%{city}%"))
        if country:
            query = query.filter(AirQualityLocation.country == country.upper())
        if parameter:
            query = query.filter(AirQualityMeasurement.parameter == parameter)

        query = query.order_by(AirQualityMeasurement.timestamp.desc()).limit(1000)

        results = query.all()

        readings = [
            AirQualityRecord(
                location_id=r.location_id,
                location_name=r.location.name if r.location else None,
                city=r.location.city if r.location else None,
                country=r.location.country if r.location else None,
                timestamp=r.timestamp,
                parameter=r.parameter,
                value=r.value,
                unit=r.unit,
                aqi=r.aqi,
            )
            for r in results
        ]

        return AirQualityResponse(
            city=city,
            country=country,
            date=query_date,
            readings=readings,
            total=len(readings),
        )
    finally:
        session.close()


# ===========================================
# PHASE 2 ENDPOINTS
# ===========================================

@app.get("/api/v1/weather/observations", response_model=WeatherResponse, tags=["Weather"])
async def get_weather_observations(
    city: str = Query(..., description="City name"),
    query_date: date = Query(..., alias="date", description="Date to query"),
    api_key: str = Depends(verify_api_key),
):
    """Get weather observations for a city."""
    session = SessionLocal()
    try:
        query = (
            session.query(WeatherObservation)
            .filter(
                WeatherObservation.city.ilike(f"%{city}%"),
                func.date(WeatherObservation.timestamp) == query_date,
            )
            .order_by(WeatherObservation.timestamp)
        )

        results = query.all()

        observations = [
            WeatherRecord(
                city=r.city,
                timestamp=r.timestamp,
                temp_c=r.temp_c,
                temp_feels_like_c=r.temp_feels_like_c,
                humidity_pct=r.humidity_pct,
                wind_speed_ms=r.wind_speed_ms,
                weather_main=r.weather_main,
                pressure_hpa=r.pressure_hpa,
            )
            for r in results
        ]

        return WeatherResponse(
            city=city,
            date=query_date,
            observations=observations,
            total=len(observations),
        )
    finally:
        session.close()


@app.get("/api/v1/weather/forecast", response_model=WeatherForecastResponse, tags=["Weather"])
async def get_weather_forecast(
    city: str = Query(..., description="City name"),
    days: int = Query(7, ge=1, le=14, description="Number of days"),
    api_key: str = Depends(verify_api_key),
):
    """Get weather forecast for a city."""
    session = SessionLocal()
    try:
        start_datetime = datetime.combine(date.today(), datetime.min.time())
        end_datetime = datetime.combine(date.today() + timedelta(days=days), datetime.max.time())

        query = (
            session.query(WeatherForecast)
            .filter(
                WeatherForecast.city.ilike(f"%{city}%"),
                WeatherForecast.forecast_timestamp >= start_datetime,
                WeatherForecast.forecast_timestamp <= end_datetime,
            )
            .order_by(WeatherForecast.forecast_timestamp)
        )

        results = query.all()

        forecasts = [
            WeatherForecastRecord(
                city=r.city,
                forecast_timestamp=r.forecast_timestamp,
                temp_c=r.temp_c,
                humidity_pct=r.humidity_pct,
                wind_speed_ms=r.wind_speed_ms,
                weather_main=r.weather_main,
                pop=r.pop,
            )
            for r in results
        ]

        return WeatherForecastResponse(
            city=city,
            forecasts=forecasts,
            total=len(forecasts),
        )
    finally:
        session.close()


@app.get("/api/v1/trends/interest", response_model=TrendResponse, tags=["Trends"])
async def get_trend_interest(
    keyword: str = Query(..., description="Search keyword"),
    geo: Optional[str] = Query("US", description="Geographic region"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    api_key: str = Depends(verify_api_key),
):
    """Get Google Trends interest data for a keyword."""
    session = SessionLocal()
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=90)

        # Query TrendInterest directly by keyword string
        query = (
            session.query(TrendInterest)
            .filter(
                TrendInterest.keyword.ilike(keyword),
                TrendInterest.date >= start_date,
                TrendInterest.date <= end_date,
            )
        )

        if geo:
            query = query.filter(TrendInterest.geo == geo)

        query = query.order_by(TrendInterest.date)
        results = query.all()

        data = [
            TrendRecord(
                keyword=r.keyword,
                date=r.date,
                interest=r.interest,
                is_partial=r.is_partial or False,
                geo=r.geo,
            )
            for r in results
        ]

        return TrendResponse(
            keyword=keyword,
            geo=geo,
            data=data,
            total=len(data),
        )
    finally:
        session.close()


@app.get("/api/v1/sentiment/ticker", response_model=SentimentResponse, tags=["Sentiment"])
async def get_ticker_sentiment(
    ticker: str = Query(..., description="Stock ticker"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    api_key: str = Depends(verify_api_key),
):
    """Get Reddit sentiment data for a ticker."""
    session = SessionLocal()
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        query = (
            session.query(TickerSentimentDaily)
            .filter(
                TickerSentimentDaily.ticker == ticker.upper(),
                TickerSentimentDaily.date >= start_date,
                TickerSentimentDaily.date <= end_date,
            )
        )

        query = query.order_by(TickerSentimentDaily.date)
        results = query.all()

        data = [
            SentimentRecord(
                ticker=r.ticker,
                date=r.date,
                avg_sentiment=r.avg_sentiment,
                mention_count=r.mention_count,
                positive_mentions=r.positive_mentions,
                negative_mentions=r.negative_mentions,
                neutral_mentions=r.neutral_mentions,
            )
            for r in results
        ]

        return SentimentResponse(
            ticker=ticker,
            data=data,
            total=len(data),
        )
    finally:
        session.close()


@app.get("/api/v1/shipping/ports", response_model=PortListResponse, tags=["Shipping"])
async def list_ports(
    country: Optional[str] = Query(None, description="Filter by country code"),
    port_type: Optional[str] = Query(None, description="Filter by port type"),
    api_key: str = Depends(verify_api_key),
):
    """List tracked ports."""
    session = SessionLocal()
    try:
        query = session.query(Port)

        if country:
            query = query.filter(Port.country == country.upper())
        if port_type:
            query = query.filter(Port.port_type == port_type)

        results = query.all()

        ports = [
            PortRecord(
                port_id=p.port_id,
                port_name=p.port_name,
                country=p.country,
                latitude=p.latitude,
                longitude=p.longitude,
                port_type=p.port_type,
            )
            for p in results
        ]

        return PortListResponse(ports=ports, total=len(ports))
    finally:
        session.close()


@app.get("/api/v1/shipping/congestion", response_model=CongestionResponse, tags=["Shipping"])
async def get_port_congestion(
    port_id: Optional[str] = Query(None, description="Port ID"),
    query_date: date = Query(..., alias="date", description="Date to query"),
    api_key: str = Depends(verify_api_key),
):
    """Get port congestion data."""
    session = SessionLocal()
    try:
        query = (
            session.query(PortCongestion)
            .filter(PortCongestion.date == query_date)
        )

        if port_id:
            query = query.filter(PortCongestion.port_id == port_id)

        results = query.all()

        data = [
            CongestionRecord(
                port_id=r.port_id,
                port_name=r.port.port_name if r.port else None,
                date=r.date,
                congestion_index=r.congestion_index,
                vessels_waiting=r.vessels_waiting,
                avg_wait_hours=r.avg_wait_hours,
            )
            for r in results
        ]

        return CongestionResponse(
            port_id=port_id,
            date=query_date,
            data=data,
            total=len(data),
        )
    finally:
        session.close()


@app.get("/api/v1/github/repos", response_model=GitHubRepoListResponse, tags=["GitHub"])
async def list_github_repos(
    company: Optional[str] = Query(None, description="Filter by company"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    api_key: str = Depends(verify_api_key),
):
    """List tracked GitHub repositories."""
    session = SessionLocal()
    try:
        query = session.query(GitHubRepository)

        if company:
            query = query.filter(GitHubRepository.company.ilike(f"%{company}%"))
        if ticker:
            query = query.filter(GitHubRepository.ticker == ticker.upper())

        results = query.all()

        repos = [
            GitHubRepoRecord(
                full_name=r.full_name,
                company=r.company,
                ticker=r.ticker,
                stars=None,  # Available in GitHubRepoMetrics
                forks=None,  # Available in GitHubRepoMetrics
                open_issues=None,  # Available in GitHubRepoMetrics
                language=r.language,
            )
            for r in results
        ]

        return GitHubRepoListResponse(repos=repos, total=len(repos))
    finally:
        session.close()


@app.get("/api/v1/github/activity", response_model=GitHubActivityResponse, tags=["GitHub"])
async def get_github_activity(
    repo: str = Query(..., description="Repository full name (owner/repo)"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    api_key: str = Depends(verify_api_key),
):
    """Get GitHub activity metrics for a repository."""
    session = SessionLocal()
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        query = (
            session.query(GitHubRepoMetrics)
            .filter(
                GitHubRepoMetrics.full_name == repo,
                GitHubRepoMetrics.date >= start_date,
                GitHubRepoMetrics.date <= end_date,
            )
            .order_by(GitHubRepoMetrics.date)
        )

        results = query.all()

        data = [
            GitHubActivityRecord(
                full_name=r.full_name,
                date=r.date,
                commits_24h=r.commits_24h,
                prs_opened_24h=r.prs_opened_24h,
                prs_merged_24h=r.prs_merged_24h,
                issues_opened_24h=r.issues_opened_24h,
                unique_committers_24h=r.unique_committers_24h,
            )
            for r in results
        ]

        return GitHubActivityResponse(
            repo=repo,
            data=data,
            total=len(data),
        )
    finally:
        session.close()


@app.get("/api/v1/satellite/parking", response_model=ParkingResponse, tags=["Satellite"])
async def get_parking_data(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    api_key: str = Depends(verify_api_key),
):
    """Get satellite parking lot occupancy data."""
    session = SessionLocal()
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        query = (
            session.query(ParkingLotMetrics)
            .join(SatelliteLocation, ParkingLotMetrics.location_id == SatelliteLocation.location_id)
            .filter(
                ParkingLotMetrics.observation_date >= start_date,
                ParkingLotMetrics.observation_date <= end_date,
            )
        )

        if ticker:
            query = query.filter(ParkingLotMetrics.ticker == ticker.upper())

        query = query.order_by(ParkingLotMetrics.observation_date.desc())
        results = query.all()

        data = [
            ParkingRecord(
                location_id=r.location_id,
                location_name=r.location.name if r.location else None,
                ticker=r.ticker,
                date=r.observation_date,
                occupancy_rate=r.occupancy_rate,
                cars_detected=r.cars_detected,
                confidence_score=r.confidence_score,
            )
            for r in results
        ]

        return ParkingResponse(
            ticker=ticker,
            data=data,
            total=len(data),
        )
    finally:
        session.close()


@app.get("/api/v1/satellite/agriculture", response_model=AgriculturalResponse, tags=["Satellite"])
async def get_agricultural_data(
    region: str = Query(..., description="Agricultural region"),
    crop_type: Optional[str] = Query(None, description="Crop type"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    api_key: str = Depends(verify_api_key),
):
    """Get satellite agricultural/NDVI data."""
    session = SessionLocal()
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=90)

        query = (
            session.query(AgriculturalMetrics)
            .filter(
                AgriculturalMetrics.region.ilike(f"%{region}%"),
                AgriculturalMetrics.observation_date >= start_date,
                AgriculturalMetrics.observation_date <= end_date,
            )
        )

        if crop_type:
            query = query.filter(AgriculturalMetrics.crop_type == crop_type)

        query = query.order_by(AgriculturalMetrics.observation_date)
        results = query.all()

        data = [
            AgriculturalRecord(
                location_id=r.location_id,
                region=r.region,
                crop_type=r.crop_type,
                date=r.observation_date,
                ndvi_mean=r.ndvi_mean,
                crop_health_score=r.crop_health_score,
                ndvi_vs_historical=r.ndvi_vs_historical,
            )
            for r in results
        ]

        return AgriculturalResponse(
            region=region,
            crop_type=crop_type,
            data=data,
            total=len(data),
        )
    finally:
        session.close()


# ===========================================
# ENTRY POINT
# ===========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )

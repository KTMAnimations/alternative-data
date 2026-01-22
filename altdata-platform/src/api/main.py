"""FastAPI application for the Alternative Data Platform."""

from datetime import datetime, timedelta
from typing import List, Optional

import redis
from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.database import get_db, check_database_connection, SessionLocal
from src.models.schemas import Entity, Factor, FactorDefinition
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

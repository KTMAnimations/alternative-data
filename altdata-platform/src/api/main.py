"""FastAPI application for the Alternative Data Platform."""

from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.models.database import get_db, check_database_connection

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


# ===========================================
# SCHEMAS
# ===========================================

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    database: str
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
    
    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        timestamp=datetime.utcnow(),
        database=db_status,
        version="1.0.0",
    )


@app.get("/api/v1/factors", response_model=FactorListResponse, tags=["Factors"])
async def list_factors(
    category: Optional[str] = Query(None, description="Filter by category"),
    api_key: str = Depends(verify_api_key),
):
    """List all available factors."""
    # TODO: Query from database
    # For MVP, return hardcoded list
    factors = [
        FactorListItem(
            id="insider_transaction_momentum",
            name="Insider Transaction Momentum",
            description="Net insider buying/selling from Form 4 filings over 30 days",
            category="sec",
            frequency="daily",
        ),
        FactorListItem(
            id="insider_clustering_score",
            name="Insider Clustering Score",
            description="Number of unique insiders trading in same direction within 7 days",
            category="sec",
            frequency="daily",
        ),
        FactorListItem(
            id="8k_event_velocity",
            name="8-K Event Velocity",
            description="Number of 8-K filings in rolling 30-day window",
            category="sec",
            frequency="daily",
        ),
        FactorListItem(
            id="yield_curve_slope",
            name="Yield Curve Slope",
            description="10Y Treasury minus 2Y Treasury yield",
            category="macro",
            frequency="daily",
        ),
        FactorListItem(
            id="credit_spread_index",
            name="Credit Spread Index",
            description="BAA corporate bond spread over 10Y Treasury",
            category="macro",
            frequency="daily",
        ),
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
    # TODO: Query from database
    # For MVP, return mock data
    
    valid_factors = [
        "insider_transaction_momentum",
        "insider_clustering_score", 
        "8k_event_velocity",
        "yield_curve_slope",
        "credit_spread_index",
    ]
    
    if factor_name not in valid_factors:
        raise HTTPException(status_code=404, detail=f"Factor '{factor_name}' not found")
    
    # Mock response
    return FactorResponse(
        factor_name=factor_name,
        entity_id=entity_id,
        entity_type="company",
        values=[
            FactorValue(date=datetime(2024, 1, 15), value=1250000.0),
            FactorValue(date=datetime(2024, 1, 16), value=980000.0),
            FactorValue(date=datetime(2024, 1, 17), value=1100000.0),
        ],
        metadata={
            "computed_at": datetime.utcnow().isoformat(),
            "data_freshness": "2024-01-17T23:59:59Z",
        }
    )


@app.get("/api/v1/entities", response_model=EntityListResponse, tags=["Entities"])
async def list_entities(
    search: Optional[str] = Query(None, description="Search by name or ticker"),
    entity_type: Optional[str] = Query(None, description="Filter by type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    api_key: str = Depends(verify_api_key),
):
    """List and search entities."""
    # TODO: Query from database
    # Mock response
    entities = [
        EntityResponse(
            id="AAPL",
            name="Apple Inc.",
            ticker="AAPL",
            entity_type="company",
            sector="Technology",
            industry="Consumer Electronics",
        ),
        EntityResponse(
            id="TSLA",
            name="Tesla, Inc.",
            ticker="TSLA",
            entity_type="company",
            sector="Consumer Cyclical",
            industry="Auto Manufacturers",
        ),
    ]
    
    if search:
        search_lower = search.lower()
        entities = [
            e for e in entities 
            if search_lower in e.name.lower() or search_lower in (e.ticker or "").lower()
        ]
    
    return EntityListResponse(
        entities=entities,
        total=len(entities),
        page=page,
        page_size=page_size,
    )


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
    # TODO: Query from database
    
    # Mock for known entities
    entities = {
        "AAPL": EntityResponse(
            id="AAPL",
            name="Apple Inc.",
            ticker="AAPL",
            entity_type="company",
            sector="Technology",
            industry="Consumer Electronics",
        ),
        "TSLA": EntityResponse(
            id="TSLA",
            name="Tesla, Inc.",
            ticker="TSLA",
            entity_type="company",
            sector="Consumer Cyclical",
            industry="Auto Manufacturers",
        ),
    }
    
    if entity_id not in entities:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    
    return entities[entity_id]


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
            },
            {
                "id": "fred",
                "name": "FRED",
                "category": "macroeconomic",
                "status": "active",
                "update_frequency": "daily",
            },
            {
                "id": "adsb_exchange",
                "name": "ADS-B Exchange",
                "category": "aviation",
                "status": "planned",
                "update_frequency": "real-time",
            },
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

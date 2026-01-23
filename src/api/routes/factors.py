"""Factor API routes."""

import io
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.factors import Factor, FactorValue, FactorRelationship, FactorDomain

router = APIRouter()


class ResponseFormat(str, Enum):
    """Supported response formats for factor history (US-023)."""

    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    ARROW = "arrow"


# ETF to constituent ticker mappings (US-024)
ETF_CONSTITUENT_WEIGHTS: dict[str, dict[str, float]] = {
    # Airlines ETF
    "JETS": {
        "DAL": 0.12,    # Delta Air Lines
        "UAL": 0.11,    # United Airlines
        "LUV": 0.10,    # Southwest Airlines
        "AAL": 0.09,    # American Airlines
        "JBLU": 0.05,   # JetBlue Airways
        "ALK": 0.04,    # Alaska Air Group
        "SAVE": 0.03,   # Spirit Airlines
        "HA": 0.02,     # Hawaiian Holdings
    },
    # Restaurant/Consumer ETF
    "PEJ": {
        "DRI": 0.08,    # Darden Restaurants
        "MCD": 0.12,    # McDonald's
        "SBUX": 0.10,   # Starbucks
        "CMG": 0.07,    # Chipotle
        "YUM": 0.08,    # Yum! Brands
        "QSR": 0.05,    # Restaurant Brands
        "DPZ": 0.04,    # Domino's Pizza
        "WEN": 0.03,    # Wendy's
    },
    # Homebuilder ETF
    "XHB": {
        "DHI": 0.10,    # D.R. Horton
        "LEN": 0.09,    # Lennar
        "PHM": 0.07,    # PulteGroup
        "NVR": 0.06,    # NVR Inc
        "TOL": 0.05,    # Toll Brothers
        "HD": 0.08,     # Home Depot
        "LOW": 0.07,    # Lowe's
    },
    # REIT ETF (Residential)
    "REZ": {
        "EQR": 0.15,    # Equity Residential
        "AVB": 0.14,    # AvalonBay
        "MAA": 0.10,    # Mid-America Apartment
        "INVH": 0.08,   # Invitation Homes
        "AMH": 0.07,    # American Homes 4 Rent
        "UDR": 0.06,    # UDR Inc
        "CPT": 0.05,    # Camden Property Trust
    },
    # Entertainment/Media ETF
    "PBS": {
        "DIS": 0.15,    # Disney
        "WBD": 0.08,    # Warner Bros Discovery
        "PARA": 0.06,   # Paramount Global
        "CMCSA": 0.12,  # Comcast
        "SONY": 0.07,   # Sony (placeholder for ADR)
        "NFLX": 0.10,   # Netflix
    },
    # Insurance ETF
    "IAK": {
        "ALL": 0.12,    # Allstate
        "TRV": 0.11,    # Travelers
        "CB": 0.10,     # Chubb
        "PGR": 0.14,    # Progressive
        "AIG": 0.08,    # AIG
        "MET": 0.07,    # MetLife
    },
    # Cybersecurity ETF
    "CIBR": {
        "NET": 0.10,    # Cloudflare
        "CRWD": 0.12,   # CrowdStrike
        "PANW": 0.11,   # Palo Alto Networks
        "ZS": 0.09,     # Zscaler
        "FTNT": 0.08,   # Fortinet
        "OKTA": 0.06,   # Okta
    },
}


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


@router.get("/{factor_id}/history", response_model=None)
async def get_factor_history(
    factor_id: str,
    tickers: str = Query(..., description="Comma-separated list of tickers"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    cursor: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=10000),
    format: ResponseFormat = Query(
        ResponseFormat.JSON,
        description="Response format: json, csv, parquet, or arrow",
    ),
    expand_etf: bool = Query(
        False,
        description="Expand ETF tickers to constituents with weighted average",
    ),
    db: AsyncSession = Depends(get_db),
) -> Union[FactorHistoryResponse, Response]:
    """Query historical factor values (US-023).

    Supports multiple response formats:
    - JSON: Default structured response with pagination
    - CSV: Comma-separated values for spreadsheet import
    - Parquet: Columnar format for efficient analytics
    - Arrow: Apache Arrow format for high-performance data exchange

    ETF tickers can be expanded to their constituents with weighted averages
    when expand_etf=true.
    """
    # Get factor
    factor_query = select(Factor).where(Factor.factor_id == factor_id)
    factor_result = await db.execute(factor_query)
    factor = factor_result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    # Parse and expand tickers
    ticker_list = [t.strip().upper() for t in tickers.split(",")]

    # Expand ETF tickers if requested (US-024)
    etf_tickers = {}
    if expand_etf:
        expanded_tickers = []
        for ticker in ticker_list:
            if ticker in ETF_CONSTITUENT_WEIGHTS:
                etf_tickers[ticker] = ETF_CONSTITUENT_WEIGHTS[ticker]
                expanded_tickers.extend(ETF_CONSTITUENT_WEIGHTS[ticker].keys())
            else:
                expanded_tickers.append(ticker)
        ticker_list = list(set(expanded_tickers))

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

    # Build response data
    data_list = [
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
    ]

    # Compute ETF weighted averages if needed (US-024)
    if etf_tickers:
        etf_data = _compute_etf_weighted_averages(data_list, etf_tickers, factor_id)
        data_list.extend(etf_data)

    # Return response in requested format
    if format == ResponseFormat.JSON:
        return FactorHistoryResponse(
            factor_id=factor_id,
            data=data_list,
            total_count=len(data_list),
            cursor=next_cursor,
        )
    elif format == ResponseFormat.CSV:
        return _format_csv_response(data_list, factor_id)
    elif format == ResponseFormat.PARQUET:
        return _format_parquet_response(data_list, factor_id)
    elif format == ResponseFormat.ARROW:
        return _format_arrow_response(data_list, factor_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}",
        )


def _compute_etf_weighted_averages(
    data: list[FactorValueResponse],
    etf_tickers: dict[str, dict[str, float]],
    factor_id: str,
) -> list[FactorValueResponse]:
    """Compute weighted average factor values for ETF tickers (US-024).

    Args:
        data: List of constituent factor values.
        etf_tickers: Mapping of ETF ticker to constituent weights.
        factor_id: Factor ID for the response.

    Returns:
        List of ETF-level factor values with weighted averages.
    """
    from collections import defaultdict

    etf_results = []

    # Group data by date and ticker
    by_date_ticker: dict[date, dict[str, FactorValueResponse]] = defaultdict(dict)
    for item in data:
        by_date_ticker[item.as_of_date][item.ticker] = item

    # Compute weighted average for each ETF for each date
    for as_of_date, ticker_data in by_date_ticker.items():
        for etf_ticker, weights in etf_tickers.items():
            weighted_mean = 0.0
            weighted_variance = 0.0
            total_weight = 0.0
            min_data_quality = 1.0
            constituent_count = 0

            for constituent, weight in weights.items():
                if constituent in ticker_data:
                    item = ticker_data[constituent]
                    weighted_mean += weight * item.mean
                    # Variance of weighted sum (assuming independence)
                    weighted_variance += (weight ** 2) * item.variance
                    total_weight += weight
                    min_data_quality = min(min_data_quality, item.data_quality)
                    constituent_count += 1

            # Only create ETF entry if we have at least some constituents
            if constituent_count > 0 and total_weight > 0:
                # Normalize by total weight if not all constituents present
                normalized_mean = weighted_mean / total_weight
                normalized_variance = weighted_variance / (total_weight ** 2)

                etf_results.append(
                    FactorValueResponse(
                        ticker=etf_ticker,
                        factor_id=factor_id,
                        as_of_date=as_of_date,
                        mean=normalized_mean,
                        variance=normalized_variance,
                        data_quality=min_data_quality * (constituent_count / len(weights)),
                        revision_status="computed",
                    )
                )

    return etf_results


def _format_csv_response(data: list[FactorValueResponse], factor_id: str) -> Response:
    """Format factor history as CSV (US-023).

    Args:
        data: List of factor values.
        factor_id: Factor ID for filename.

    Returns:
        Streaming response with CSV content.
    """
    output = io.StringIO()
    output.write("ticker,factor_id,as_of_date,mean,variance,data_quality,revision_status\n")

    for item in data:
        output.write(
            f"{item.ticker},{item.factor_id},{item.as_of_date},"
            f"{item.mean},{item.variance},{item.data_quality},{item.revision_status}\n"
        )

    content = output.getvalue()
    output.close()

    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{factor_id}_history.csv"',
        },
    )


def _format_parquet_response(data: list[FactorValueResponse], factor_id: str) -> Response:
    """Format factor history as Parquet (US-023).

    Args:
        data: List of factor values.
        factor_id: Factor ID for filename.

    Returns:
        Streaming response with Parquet content.
    """
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Parquet format requires pyarrow. Install with: pip install pyarrow",
        )

    # Build Arrow table
    table = _build_arrow_table(data)

    # Write to Parquet buffer
    output = io.BytesIO()
    pq.write_table(table, output)
    content = output.getvalue()
    output.close()

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{factor_id}_history.parquet"',
        },
    )


def _format_arrow_response(data: list[FactorValueResponse], factor_id: str) -> Response:
    """Format factor history as Arrow IPC (US-023).

    Args:
        data: List of factor values.
        factor_id: Factor ID for filename.

    Returns:
        Streaming response with Arrow IPC content.
    """
    try:
        import pyarrow as pa
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Arrow format requires pyarrow. Install with: pip install pyarrow",
        )

    # Build Arrow table
    table = _build_arrow_table(data)

    # Write to Arrow IPC buffer
    output = io.BytesIO()
    writer = pa.RecordBatchStreamWriter(output, table.schema)
    writer.write_table(table)
    writer.close()
    content = output.getvalue()
    output.close()

    return Response(
        content=content,
        media_type="application/vnd.apache.arrow.stream",
        headers={
            "Content-Disposition": f'attachment; filename="{factor_id}_history.arrow"',
        },
    )


def _build_arrow_table(data: list[FactorValueResponse]):
    """Build Arrow table from factor value data.

    Args:
        data: List of factor values.

    Returns:
        PyArrow table.
    """
    import pyarrow as pa

    return pa.table({
        "ticker": [item.ticker for item in data],
        "factor_id": [item.factor_id for item in data],
        "as_of_date": [item.as_of_date.isoformat() for item in data],
        "mean": [item.mean for item in data],
        "variance": [item.variance for item in data],
        "data_quality": [item.data_quality for item in data],
        "revision_status": [item.revision_status for item in data],
    })


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


# Box Office Model Accuracy Endpoints (US-032)

class ModelAccuracyRecordRequest(BaseModel):
    """Request to record prediction accuracy."""

    prediction_date: date
    movie_title: str
    distributor_ticker: str
    predicted_gross: float
    actual_gross: float
    method_predictions: dict[str, float] = Field(default_factory=dict)


class ModelAccuracySummaryResponse(BaseModel):
    """Summary of model accuracy metrics."""

    total_predictions: int
    accuracy_data_available: bool
    ensemble_mae_pct: Optional[float] = None
    ensemble_median_error_pct: Optional[float] = None
    ensemble_std_error_pct: Optional[float] = None
    method_mae_pct: Optional[dict[str, Optional[float]]] = None
    within_10pct_accuracy: Optional[float] = None
    within_20pct_accuracy: Optional[float] = None


@router.get("/boxoffice/model-accuracy")
async def get_boxoffice_model_accuracy(
    ticker: Optional[str] = Query(None, description="Filter by distributor ticker"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get historical model accuracy for box office predictions (US-032).

    Returns the history of predictions and their actual outcomes, allowing
    users to assess model reliability and track accuracy over time.
    """
    from src.transformations.factors.boxoffice_factors import get_model_accuracy_history

    history = get_model_accuracy_history(ticker=ticker, limit=limit)

    return {
        "ticker_filter": ticker,
        "record_count": len(history),
        "records": history,
    }


@router.get("/boxoffice/model-accuracy/summary", response_model=ModelAccuracySummaryResponse)
async def get_boxoffice_model_accuracy_summary():
    """Get summary statistics of box office model accuracy (US-032).

    Returns aggregate metrics including:
    - Mean absolute error percentage for ensemble and individual methods
    - Accuracy rates (within 10%, 20% of actual)
    - Standard deviation of errors
    """
    from src.transformations.factors.boxoffice_factors import get_model_accuracy_summary

    summary = get_model_accuracy_summary()

    return ModelAccuracySummaryResponse(**summary)


@router.post("/boxoffice/model-accuracy")
async def record_boxoffice_prediction_accuracy(
    request: ModelAccuracyRecordRequest,
):
    """Record actual box office results for model accuracy tracking (US-032).

    After a weekend's actual results are known, call this endpoint to record
    the prediction vs actual for model improvement tracking.
    """
    from src.transformations.factors.boxoffice_factors import record_prediction_accuracy

    metrics = record_prediction_accuracy(
        prediction_date=request.prediction_date,
        movie_title=request.movie_title,
        distributor_ticker=request.distributor_ticker,
        predicted_gross=request.predicted_gross,
        actual_gross=request.actual_gross,
        method_predictions=request.method_predictions,
    )

    return {
        "status": "recorded",
        "movie_title": metrics.movie_title,
        "prediction_error_pct": metrics.prediction_error_pct,
        "method_errors": metrics.method_errors,
    }

"""Backtesting API routes."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
import numpy as np

from src.core.database import get_db
from src.models.factors import Factor

router = APIRouter()


# Pydantic schemas
class BacktestRequest(BaseModel):
    """Request for running a backtest."""

    factor_id: str
    start_date: date
    end_date: date


class BacktestMetrics(BaseModel):
    """Backtest performance metrics."""

    ic: float  # Information Coefficient
    ir: float  # Information Ratio
    tstat: float  # T-statistic
    hit_rate: float  # Proportion of positive returns
    ic_monthly: list[dict]  # Monthly IC time series
    decile_returns: list[float]  # Returns by decile


class BacktestResponse(BaseModel):
    """Response from backtest run."""

    factor_id: str
    start_date: date
    end_date: date
    metrics: BacktestMetrics
    warnings: list[str]


class DecayResponse(BaseModel):
    """Factor decay analysis response."""

    factor_id: str
    decay_curve: dict[str, Optional[float]]
    half_life_days: Optional[int]


class SeasonalityResponse(BaseModel):
    """Factor seasonality analysis response."""

    factor_id: str
    day_of_week_ic: dict[str, float]
    monthly_ic: dict[str, float]
    holiday_effects: list[dict]


class ResearchPackRequest(BaseModel):
    """Request for research pack export."""

    factor_id: str
    include_notebook: bool = True
    include_data: bool = True
    formats: list[str] = Field(default=["csv", "json"])


# Routes
@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    returns_file: UploadFile = File(..., description="CSV with ticker,date,return columns"),
    db: AsyncSession = Depends(get_db),
):
    """Run a factor backtest against user-provided return data."""
    # Validate factor exists
    factor_query = select(Factor).where(Factor.factor_id == request.factor_id)
    factor_result = await db.execute(factor_query)
    factor = factor_result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {request.factor_id} not found",
        )

    # Parse uploaded returns file
    try:
        content = await returns_file.read()
        returns_df = pd.read_csv(pd.io.common.BytesIO(content))

        # Validate columns
        required_cols = {"ticker", "date", "return"}
        if not required_cols.issubset(returns_df.columns):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV must contain columns: {required_cols}",
            )

        returns_df["date"] = pd.to_datetime(returns_df["date"]).dt.date
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse returns file: {str(e)}",
        )

    # Get factor values for the period
    from src.models.factors import FactorValue

    factor_query = (
        select(FactorValue)
        .where(FactorValue.factor_id == factor.id)
        .where(FactorValue.as_of_date >= request.start_date)
        .where(FactorValue.as_of_date <= request.end_date)
    )
    factor_result = await db.execute(factor_query)
    factor_values = factor_result.scalars().all()

    if not factor_values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No factor values found for {request.factor_id} in date range",
        )

    # Convert to DataFrame
    factor_df = pd.DataFrame([
        {"ticker": fv.ticker, "date": fv.as_of_date, "factor": float(fv.mean)}
        for fv in factor_values
    ])

    # Merge factor with returns
    merged = pd.merge(factor_df, returns_df, on=["ticker", "date"], how="inner")

    if len(merged) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No overlapping data between factor values and returns",
        )

    # Compute metrics
    warnings = []

    # Information Coefficient (Spearman correlation)
    ic = merged.groupby("date").apply(
        lambda x: x["factor"].corr(x["return"], method="spearman")
    ).mean()

    # IR = mean(IC) / std(IC)
    ic_series = merged.groupby("date").apply(
        lambda x: x["factor"].corr(x["return"], method="spearman")
    )
    ir = ic_series.mean() / ic_series.std() if ic_series.std() > 0 else 0

    # T-statistic
    n_periods = len(ic_series)
    tstat = ir * np.sqrt(n_periods) if n_periods > 0 else 0

    # Hit rate
    hit_rate = (ic_series > 0).mean()

    # Monthly IC
    merged["month"] = pd.to_datetime(merged["date"]).dt.to_period("M")
    monthly_ic = merged.groupby("month").apply(
        lambda x: x["factor"].corr(x["return"], method="spearman")
    ).reset_index()
    monthly_ic.columns = ["month", "ic"]
    monthly_ic_list = [
        {"month": str(row["month"]), "ic": float(row["ic"]) if pd.notna(row["ic"]) else 0}
        for _, row in monthly_ic.iterrows()
    ]

    # Decile returns
    merged["decile"] = pd.qcut(merged["factor"], 10, labels=False, duplicates="drop")
    decile_returns = merged.groupby("decile")["return"].mean().tolist()

    # Survivorship bias check
    unique_tickers_start = merged[merged["date"] <= merged["date"].min() + pd.Timedelta(days=30)]["ticker"].unique()
    unique_tickers_end = merged[merged["date"] >= merged["date"].max() - pd.Timedelta(days=30)]["ticker"].unique()
    if len(set(unique_tickers_start) - set(unique_tickers_end)) > 0:
        warnings.append("Potential survivorship bias: Some tickers present at start are missing at end")

    metrics = BacktestMetrics(
        ic=float(ic) if pd.notna(ic) else 0,
        ir=float(ir) if pd.notna(ir) else 0,
        tstat=float(tstat) if pd.notna(tstat) else 0,
        hit_rate=float(hit_rate) if pd.notna(hit_rate) else 0,
        ic_monthly=monthly_ic_list,
        decile_returns=decile_returns,
    )

    return BacktestResponse(
        factor_id=request.factor_id,
        start_date=request.start_date,
        end_date=request.end_date,
        metrics=metrics,
        warnings=warnings,
    )


@router.get("/decay/{factor_id}", response_model=DecayResponse)
async def analyze_decay(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Analyze factor signal decay over time."""
    query = select(Factor).where(Factor.factor_id == factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    return DecayResponse(
        factor_id=factor_id,
        decay_curve={
            "1d": float(factor.decay_1d) if factor.decay_1d else None,
            "2d": None,  # TODO: Compute
            "5d": float(factor.decay_5d) if factor.decay_5d else None,
            "10d": float(factor.decay_10d) if factor.decay_10d else None,
            "21d": float(factor.decay_21d) if factor.decay_21d else None,
            "63d": float(factor.decay_63d) if factor.decay_63d else None,
            "126d": None,
            "252d": None,
        },
        half_life_days=factor.estimated_half_life_days,
    )


@router.get("/seasonality/{factor_id}", response_model=SeasonalityResponse)
async def analyze_seasonality(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Analyze factor seasonality patterns."""
    query = select(Factor).where(Factor.factor_id == factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    # TODO: Compute actual seasonality from factor values
    return SeasonalityResponse(
        factor_id=factor_id,
        day_of_week_ic={
            "Monday": 0.0,
            "Tuesday": 0.0,
            "Wednesday": 0.0,
            "Thursday": 0.0,
            "Friday": 0.0,
        },
        monthly_ic={str(i): 0.0 for i in range(1, 13)},
        holiday_effects=[],
    )


@router.post("/export")
async def export_research_pack(
    request: ResearchPackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Export a research pack for a factor."""
    query = select(Factor).where(Factor.factor_id == request.factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {request.factor_id} not found",
        )

    # TODO: Generate actual research pack
    return {
        "status": "generating",
        "factor_id": request.factor_id,
        "download_url": None,  # Will be populated when ready
        "estimated_size_mb": 10,
    }

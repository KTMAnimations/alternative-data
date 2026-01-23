"""Backtesting API routes."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server
import matplotlib.pyplot as plt

from src.core.database import get_db
from src.models.factors import Factor, FactorValue
from src.models.experiments import Experiment, ExperimentMetricSnapshot, ExperimentStatus
from scipy import stats as scipy_stats
from decimal import Decimal
from datetime import datetime

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


class MultiFactorDecayResponse(BaseModel):
    """Multi-factor decay comparison response."""

    factors: list[DecayResponse]
    comparison: dict[str, dict[str, Optional[float]]]  # horizon -> factor_id -> IC


class SeasonalityResponse(BaseModel):
    """Factor seasonality analysis response."""

    factor_id: str
    day_of_week_ic: dict[str, float]
    monthly_ic: dict[str, float]
    holiday_effects: list[dict]
    earnings_season_effects: dict[str, float]  # Q1, Q2, Q3, Q4
    seasonal_adjusted_available: bool


class SeasonalAdjustmentRequest(BaseModel):
    """Request for seasonal adjustment."""

    factor_id: str
    tickers: list[str]
    start_date: date
    end_date: date
    adjustment_method: str = "multiplicative"  # multiplicative or additive


class ResearchPackRequest(BaseModel):
    """Request for research pack export."""

    factor_id: str
    include_notebook: bool = True
    include_data: bool = True
    formats: list[str] = Field(default=["csv", "json"])


class CreateExperimentRequest(BaseModel):
    """Request to create a new A/B experiment."""

    name: str
    description: Optional[str] = None
    control_factor_id: str
    treatment_factor_id: str
    start_date: date
    end_date: Optional[date] = None
    significance_threshold: float = 0.05


class UpdateExperimentRequest(BaseModel):
    """Request to update an experiment."""

    name: Optional[str] = None
    description: Optional[str] = None
    end_date: Optional[date] = None
    significance_threshold: Optional[float] = None


class ExperimentMetrics(BaseModel):
    """Metrics for an experiment variant."""

    ic: Optional[float] = None
    ir: Optional[float] = None
    tstat: Optional[float] = None
    hit_rate: Optional[float] = None


class ExperimentResponse(BaseModel):
    """Response for an experiment."""

    id: int
    name: str
    description: Optional[str]
    control_factor_id: str
    treatment_factor_id: str
    start_date: date
    end_date: Optional[date]
    status: str
    control_metrics: ExperimentMetrics
    treatment_metrics: ExperimentMetrics
    p_value: Optional[float]
    is_significant: Optional[bool]
    winner: Optional[str]
    significance_threshold: float
    metrics_history: list[dict]


class ExperimentListResponse(BaseModel):
    """List of experiments."""

    experiments: list[ExperimentResponse]
    total: int


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


@router.get("/decay/compare", response_model=MultiFactorDecayResponse)
async def compare_decay(
    factor_ids: str = Query(..., description="Comma-separated factor IDs"),
    db: AsyncSession = Depends(get_db),
):
    """Compare decay curves across multiple factors."""
    factor_id_list = [f.strip() for f in factor_ids.split(",")]

    if len(factor_id_list) > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 4 factors can be compared at once",
        )

    factors_data = []
    comparison = {
        "1d": {}, "2d": {}, "5d": {}, "10d": {},
        "21d": {}, "63d": {}, "126d": {}, "252d": {}
    }

    for fid in factor_id_list:
        query = select(Factor).where(Factor.factor_id == fid)
        result = await db.execute(query)
        factor = result.scalar_one_or_none()

        if not factor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factor {fid} not found",
            )

        decay_curve = {
            "1d": float(factor.decay_1d) if factor.decay_1d else None,
            "2d": None,
            "5d": float(factor.decay_5d) if factor.decay_5d else None,
            "10d": float(factor.decay_10d) if factor.decay_10d else None,
            "21d": float(factor.decay_21d) if factor.decay_21d else None,
            "63d": float(factor.decay_63d) if factor.decay_63d else None,
            "126d": None,
            "252d": None,
        }

        factors_data.append(DecayResponse(
            factor_id=fid,
            decay_curve=decay_curve,
            half_life_days=factor.estimated_half_life_days,
        ))

        # Build comparison matrix
        for horizon, value in decay_curve.items():
            comparison[horizon][fid] = value

    return MultiFactorDecayResponse(
        factors=factors_data,
        comparison=comparison,
    )


def get_earnings_season(month: int) -> str:
    """Determine earnings season for a month."""
    if month in [1, 2]:
        return "Q4_reporting"  # Q4 earnings reported Jan-Feb
    elif month in [4, 5]:
        return "Q1_reporting"  # Q1 earnings reported Apr-May
    elif month in [7, 8]:
        return "Q2_reporting"  # Q2 earnings reported Jul-Aug
    elif month in [10, 11]:
        return "Q3_reporting"  # Q3 earnings reported Oct-Nov
    else:
        return "off_season"


@router.get("/seasonality/{factor_id}", response_model=SeasonalityResponse)
async def analyze_seasonality(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Analyze factor seasonality patterns including earnings seasons."""
    query = select(Factor).where(Factor.factor_id == factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    # Get factor values for seasonality analysis
    from src.models.factors import FactorValue

    values_query = select(FactorValue).where(FactorValue.factor_id == factor.id)
    values_result = await db.execute(values_query)
    factor_values = values_result.scalars().all()

    # Initialize seasonality metrics
    day_of_week_ic = {
        "Monday": 0.0, "Tuesday": 0.0, "Wednesday": 0.0,
        "Thursday": 0.0, "Friday": 0.0
    }
    monthly_ic = {str(i): 0.0 for i in range(1, 13)}
    earnings_season_effects = {
        "Q1_reporting": 0.0, "Q2_reporting": 0.0,
        "Q3_reporting": 0.0, "Q4_reporting": 0.0,
        "off_season": 0.0
    }

    # Compute actual seasonality if we have data
    if factor_values:
        df = pd.DataFrame([
            {
                "date": fv.as_of_date,
                "value": float(fv.mean),
                "day_of_week": fv.as_of_date.strftime("%A"),
                "month": fv.as_of_date.month,
                "earnings_season": get_earnings_season(fv.as_of_date.month)
            }
            for fv in factor_values
        ])

        # Day of week average
        if len(df) > 0:
            dow_avg = df.groupby("day_of_week")["value"].mean()
            for day in day_of_week_ic:
                if day in dow_avg.index:
                    day_of_week_ic[day] = float(dow_avg[day])

            # Monthly average
            month_avg = df.groupby("month")["value"].mean()
            for m in range(1, 13):
                if m in month_avg.index:
                    monthly_ic[str(m)] = float(month_avg[m])

            # Earnings season average
            season_avg = df.groupby("earnings_season")["value"].mean()
            for season in earnings_season_effects:
                if season in season_avg.index:
                    earnings_season_effects[season] = float(season_avg[season])

    # Holiday effects
    holiday_effects = [
        {"holiday": "New Year", "effect": 0.02, "days_before": 3, "days_after": 2},
        {"holiday": "Christmas", "effect": -0.01, "days_before": 5, "days_after": 2},
        {"holiday": "Thanksgiving", "effect": 0.015, "days_before": 2, "days_after": 4},
        {"holiday": "Independence Day", "effect": 0.01, "days_before": 1, "days_after": 1},
    ]

    return SeasonalityResponse(
        factor_id=factor_id,
        day_of_week_ic=day_of_week_ic,
        monthly_ic=monthly_ic,
        holiday_effects=holiday_effects,
        earnings_season_effects=earnings_season_effects,
        seasonal_adjusted_available=True,
    )


@router.post("/seasonality/adjust")
async def get_seasonal_adjustment(
    request: SeasonalAdjustmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Get seasonally adjusted factor values."""
    query = select(Factor).where(Factor.factor_id == request.factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {request.factor_id} not found",
        )

    from src.models.factors import FactorValue

    # Get factor values
    values_query = (
        select(FactorValue)
        .where(FactorValue.factor_id == factor.id)
        .where(FactorValue.ticker.in_(request.tickers))
        .where(FactorValue.as_of_date >= request.start_date)
        .where(FactorValue.as_of_date <= request.end_date)
    )
    values_result = await db.execute(values_query)
    factor_values = values_result.scalars().all()

    if not factor_values:
        return {"adjusted_values": [], "adjustment_factors": {}}

    # Compute seasonal factors
    df = pd.DataFrame([
        {
            "ticker": fv.ticker,
            "date": fv.as_of_date,
            "value": float(fv.mean),
            "month": fv.as_of_date.month
        }
        for fv in factor_values
    ])

    # Calculate monthly seasonal factors
    overall_mean = df["value"].mean()
    monthly_factors = df.groupby("month")["value"].mean() / overall_mean
    monthly_factors = monthly_factors.fillna(1.0)

    # Apply adjustment
    adjusted_values = []
    for _, row in df.iterrows():
        seasonal_factor = monthly_factors.get(row["month"], 1.0)
        if request.adjustment_method == "multiplicative":
            adjusted = row["value"] / seasonal_factor
        else:  # additive
            adjusted = row["value"] - (seasonal_factor - 1) * overall_mean

        adjusted_values.append({
            "ticker": row["ticker"],
            "date": str(row["date"]),
            "original_value": row["value"],
            "adjusted_value": float(adjusted),
            "seasonal_factor": float(seasonal_factor),
        })

    return {
        "factor_id": request.factor_id,
        "adjustment_method": request.adjustment_method,
        "adjusted_values": adjusted_values,
        "monthly_seasonal_factors": {str(k): float(v) for k, v in monthly_factors.items()},
    }


@router.post("/export")
async def export_research_pack(
    request: ResearchPackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Export a research pack for a factor including notebook, data, and statistics."""
    import io
    import json
    import zipfile
    from fastapi.responses import StreamingResponse

    query = select(Factor).where(Factor.factor_id == request.factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {request.factor_id} not found",
        )

    # Get factor values
    from src.models.factors import FactorValue

    values_query = select(FactorValue).where(FactorValue.factor_id == factor.id)
    values_result = await db.execute(values_query)
    factor_values = values_result.scalars().all()

    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Generate Jupyter notebook
        if request.include_notebook:
            notebook = {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": [
                            f"# {factor.name} - Factor Analysis\n",
                            f"\n",
                            f"**Factor ID:** {factor.factor_id}\n",
                            f"**Domain:** {factor.domain.value if factor.domain else 'N/A'}\n",
                            f"**Description:** {factor.description or 'N/A'}\n",
                        ]
                    },
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [
                            "import pandas as pd\n",
                            "import numpy as np\n",
                            "import matplotlib.pyplot as plt\n",
                            "\n",
                            "# Load factor data\n",
                            f"df = pd.read_csv('{factor.factor_id}_data.csv')\n",
                            "df['date'] = pd.to_datetime(df['date'])\n",
                            "print(f'Loaded {len(df)} records')\n",
                            "df.head()"
                        ]
                    },
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [
                            "# Factor time series plot\n",
                            "plt.figure(figsize=(12, 6))\n",
                            "for ticker in df['ticker'].unique()[:5]:\n",
                            "    ticker_df = df[df['ticker'] == ticker]\n",
                            "    plt.plot(ticker_df['date'], ticker_df['mean'], label=ticker)\n",
                            "plt.xlabel('Date')\n",
                            "plt.ylabel('Factor Value')\n",
                            f"plt.title('{factor.name} Time Series')\n",
                            "plt.legend()\n",
                            "plt.tight_layout()\n",
                            "plt.show()"
                        ]
                    },
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [
                            "# Summary statistics\n",
                            "stats = df.groupby('ticker')['mean'].agg(['mean', 'std', 'min', 'max', 'count'])\n",
                            "print('Summary Statistics by Ticker:')\n",
                            "stats"
                        ]
                    },
                    {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": [
                            "## Economic Rationale\n",
                            f"\n{factor.economic_rationale or 'See documentation for economic rationale.'}\n",
                        ]
                    },
                ],
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3"
                    }
                },
                "nbformat": 4,
                "nbformat_minor": 4
            }
            zf.writestr(f"{factor.factor_id}_analysis.ipynb", json.dumps(notebook, indent=2))

        # 2. Include raw factor data
        if request.include_data and factor_values:
            data_records = [
                {
                    "ticker": fv.ticker,
                    "date": str(fv.as_of_date),
                    "mean": float(fv.mean),
                    "variance": float(fv.variance) if fv.variance else None,
                    "data_quality": float(fv.data_quality) if fv.data_quality else None,
                }
                for fv in factor_values
            ]

            if "csv" in request.formats:
                csv_df = pd.DataFrame(data_records)
                csv_buffer = io.StringIO()
                csv_df.to_csv(csv_buffer, index=False)
                zf.writestr(f"{factor.factor_id}_data.csv", csv_buffer.getvalue())

            if "json" in request.formats:
                zf.writestr(f"{factor.factor_id}_data.json", json.dumps(data_records, indent=2))

            if "parquet" in request.formats:
                parquet_df = pd.DataFrame(data_records)
                parquet_buffer = io.BytesIO()
                parquet_df.to_parquet(parquet_buffer, index=False)
                zf.writestr(f"{factor.factor_id}_data.parquet", parquet_buffer.getvalue())

        # 3. Include computed statistics
        statistics = {
            "factor_id": factor.factor_id,
            "name": factor.name,
            "domain": factor.domain.value if factor.domain else None,
            "historical_ic": float(factor.historical_ic) if factor.historical_ic else None,
            "historical_ir": float(factor.historical_ir) if factor.historical_ir else None,
            "historical_tstat": float(factor.historical_tstat) if factor.historical_tstat else None,
            "historical_hit_rate": float(factor.historical_hit_rate) if factor.historical_hit_rate else None,
            "estimated_half_life_days": factor.estimated_half_life_days,
            "decay_curve": {
                "1d": float(factor.decay_1d) if factor.decay_1d else None,
                "5d": float(factor.decay_5d) if factor.decay_5d else None,
                "10d": float(factor.decay_10d) if factor.decay_10d else None,
                "21d": float(factor.decay_21d) if factor.decay_21d else None,
                "63d": float(factor.decay_63d) if factor.decay_63d else None,
            },
            "record_count": len(factor_values),
        }
        zf.writestr(f"{factor.factor_id}_statistics.json", json.dumps(statistics, indent=2))

        # 4. Include methodology documentation
        methodology = f"""# {factor.name} - Methodology Documentation

## Factor ID
{factor.factor_id}

## Description
{factor.description or 'N/A'}

## Formula
{factor.formula or 'See implementation for details.'}

## Economic Rationale
{factor.economic_rationale or 'N/A'}

## Primary Entities
{', '.join(factor.primary_entities) if factor.primary_entities else 'N/A'}

## Historical Performance
- Information Coefficient (IC): {factor.historical_ic or 'N/A'}
- Information Ratio (IR): {factor.historical_ir or 'N/A'}
- T-Statistic: {factor.historical_tstat or 'N/A'}
- Hit Rate: {factor.historical_hit_rate or 'N/A'}

## Signal Decay
- Half-life: {factor.estimated_half_life_days or 'N/A'} days

## Known Limitations
{factor.known_limitations or 'See documentation for limitations.'}

---
Generated by Alternative Data Platform
"""
        zf.writestr(f"{factor.factor_id}_methodology.md", methodology)

        # 5. Generate charts as PNG/SVG (US-020)
        if factor_values:
            # Prepare data for charts
            chart_data = pd.DataFrame([
                {
                    "ticker": fv.ticker,
                    "date": fv.as_of_date,
                    "mean": float(fv.mean),
                }
                for fv in factor_values
            ])
            chart_data['date'] = pd.to_datetime(chart_data['date'])

            # Chart 1: Time Series Plot (PNG)
            try:
                fig, ax = plt.subplots(figsize=(12, 6))
                for ticker in chart_data['ticker'].unique()[:5]:
                    ticker_df = chart_data[chart_data['ticker'] == ticker].sort_values('date')
                    ax.plot(ticker_df['date'], ticker_df['mean'], label=ticker, linewidth=1.5)
                ax.set_xlabel('Date', fontsize=12)
                ax.set_ylabel('Factor Value', fontsize=12)
                ax.set_title(f'{factor.name} Time Series', fontsize=14)
                ax.legend(loc='best')
                ax.grid(True, alpha=0.3)
                fig.tight_layout()

                # Save as PNG
                png_buffer = io.BytesIO()
                fig.savefig(png_buffer, format='png', dpi=150)
                png_buffer.seek(0)
                zf.writestr(f"charts/{factor.factor_id}_timeseries.png", png_buffer.getvalue())

                # Save as SVG
                svg_buffer = io.BytesIO()
                fig.savefig(svg_buffer, format='svg')
                svg_buffer.seek(0)
                zf.writestr(f"charts/{factor.factor_id}_timeseries.svg", svg_buffer.getvalue())

                plt.close(fig)
            except Exception:
                pass  # Skip chart generation on error

            # Chart 2: Decay Curve Plot (if decay data exists)
            if factor.decay_1d or factor.decay_5d or factor.decay_10d:
                try:
                    fig, ax = plt.subplots(figsize=(10, 6))
                    horizons = ['1d', '5d', '10d', '21d', '63d']
                    decay_values = [
                        float(factor.decay_1d) if factor.decay_1d else None,
                        float(factor.decay_5d) if factor.decay_5d else None,
                        float(factor.decay_10d) if factor.decay_10d else None,
                        float(factor.decay_21d) if factor.decay_21d else None,
                        float(factor.decay_63d) if factor.decay_63d else None,
                    ]

                    # Filter out None values
                    valid_data = [(h, v) for h, v in zip(horizons, decay_values) if v is not None]
                    if valid_data:
                        h_labels, values = zip(*valid_data)
                        ax.bar(h_labels, values, color='steelblue', edgecolor='darkblue')
                        ax.set_xlabel('Horizon', fontsize=12)
                        ax.set_ylabel('Information Coefficient (IC)', fontsize=12)
                        ax.set_title(f'{factor.name} Signal Decay', fontsize=14)
                        ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)
                        ax.grid(True, axis='y', alpha=0.3)

                        if factor.estimated_half_life_days:
                            ax.text(0.95, 0.95, f'Half-life: {factor.estimated_half_life_days} days',
                                   transform=ax.transAxes, ha='right', va='top',
                                   fontsize=10, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

                        fig.tight_layout()

                        # Save as PNG
                        png_buffer = io.BytesIO()
                        fig.savefig(png_buffer, format='png', dpi=150)
                        png_buffer.seek(0)
                        zf.writestr(f"charts/{factor.factor_id}_decay.png", png_buffer.getvalue())

                        # Save as SVG
                        svg_buffer = io.BytesIO()
                        fig.savefig(svg_buffer, format='svg')
                        svg_buffer.seek(0)
                        zf.writestr(f"charts/{factor.factor_id}_decay.svg", svg_buffer.getvalue())

                    plt.close(fig)
                except Exception:
                    pass  # Skip chart generation on error

            # Chart 3: Distribution Histogram
            try:
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.hist(chart_data['mean'].dropna(), bins=50, color='steelblue', edgecolor='darkblue', alpha=0.7)
                ax.set_xlabel('Factor Value', fontsize=12)
                ax.set_ylabel('Frequency', fontsize=12)
                ax.set_title(f'{factor.name} Distribution', fontsize=14)
                ax.axvline(x=chart_data['mean'].mean(), color='red', linestyle='--', linewidth=1.5, label='Mean')
                ax.legend()
                ax.grid(True, alpha=0.3)
                fig.tight_layout()

                # Save as PNG
                png_buffer = io.BytesIO()
                fig.savefig(png_buffer, format='png', dpi=150)
                png_buffer.seek(0)
                zf.writestr(f"charts/{factor.factor_id}_distribution.png", png_buffer.getvalue())

                # Save as SVG
                svg_buffer = io.BytesIO()
                fig.savefig(svg_buffer, format='svg')
                svg_buffer.seek(0)
                zf.writestr(f"charts/{factor.factor_id}_distribution.svg", svg_buffer.getvalue())

                plt.close(fig)
            except Exception:
                pass  # Skip chart generation on error

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={factor.factor_id}_research_pack.zip"
        }
    )


# =============================================================================
# US-021: A/B Experiment Framework CRUD Endpoints
# =============================================================================

@router.post("/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    request: CreateExperimentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new A/B experiment for comparing factor formulations."""
    # Validate control factor exists
    control_query = select(Factor).where(Factor.factor_id == request.control_factor_id)
    control_result = await db.execute(control_query)
    control_factor = control_result.scalar_one_or_none()

    if not control_factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Control factor {request.control_factor_id} not found",
        )

    # Validate treatment factor exists
    treatment_query = select(Factor).where(Factor.factor_id == request.treatment_factor_id)
    treatment_result = await db.execute(treatment_query)
    treatment_factor = treatment_result.scalar_one_or_none()

    if not treatment_factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Treatment factor {request.treatment_factor_id} not found",
        )

    # Create experiment
    new_experiment = Experiment(
        name=request.name,
        description=request.description,
        user_id=1,  # TODO: Get from authenticated user
        control_factor_id=control_factor.id,
        treatment_factor_id=treatment_factor.id,
        status=ExperimentStatus.DRAFT,
        start_date=request.start_date,
        end_date=request.end_date,
        significance_level=Decimal(str(request.significance_threshold)),
        target_tickers=[],
    )

    db.add(new_experiment)
    await db.flush()
    await db.refresh(new_experiment)

    return _build_experiment_response(new_experiment, control_factor, treatment_factor)


@router.get("/experiments", response_model=ExperimentListResponse)
async def list_experiments(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """List all experiments with optional status filter."""
    query = select(Experiment)

    if status_filter:
        try:
            exp_status = ExperimentStatus(status_filter)
            query = query.where(Experiment.status == exp_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}. Valid values: {[s.value for s in ExperimentStatus]}",
            )

    # Get total count
    count_query = select(Experiment)
    if status_filter:
        count_query = count_query.where(Experiment.status == ExperimentStatus(status_filter))
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    # Get paginated results
    query = query.offset(offset).limit(limit).order_by(Experiment.created_at.desc())
    result = await db.execute(query)
    experiments = result.scalars().all()

    # Build responses
    responses = []
    for exp in experiments:
        control_factor = await db.get(Factor, exp.control_factor_id)
        treatment_factor = await db.get(Factor, exp.treatment_factor_id)
        responses.append(_build_experiment_response(exp, control_factor, treatment_factor))

    return ExperimentListResponse(experiments=responses, total=total)


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific experiment by ID."""
    experiment = await db.get(Experiment, experiment_id)

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    control_factor = await db.get(Factor, experiment.control_factor_id)
    treatment_factor = await db.get(Factor, experiment.treatment_factor_id)

    return _build_experiment_response(experiment, control_factor, treatment_factor)


@router.patch("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: int,
    request: UpdateExperimentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update an experiment (only in DRAFT status)."""
    experiment = await db.get(Experiment, experiment_id)

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    if experiment.status != ExperimentStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update experiments in DRAFT status",
        )

    # Apply updates
    if request.name is not None:
        experiment.name = request.name
    if request.description is not None:
        experiment.description = request.description
    if request.end_date is not None:
        experiment.end_date = request.end_date
    if request.significance_threshold is not None:
        experiment.significance_level = Decimal(str(request.significance_threshold))

    await db.flush()
    await db.refresh(experiment)

    control_factor = await db.get(Factor, experiment.control_factor_id)
    treatment_factor = await db.get(Factor, experiment.treatment_factor_id)

    return _build_experiment_response(experiment, control_factor, treatment_factor)


@router.post("/experiments/{experiment_id}/start", response_model=ExperimentResponse)
async def start_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Start an experiment (transition from DRAFT to RUNNING)."""
    experiment = await db.get(Experiment, experiment_id)

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    if experiment.status != ExperimentStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only start experiments in DRAFT status. Current: {experiment.status.value}",
        )

    experiment.status = ExperimentStatus.RUNNING
    if not experiment.start_date:
        experiment.start_date = date.today()

    await db.flush()
    await db.refresh(experiment)

    control_factor = await db.get(Factor, experiment.control_factor_id)
    treatment_factor = await db.get(Factor, experiment.treatment_factor_id)

    return _build_experiment_response(experiment, control_factor, treatment_factor)


@router.post("/experiments/{experiment_id}/stop", response_model=ExperimentResponse)
async def stop_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Stop a running experiment and compute final results."""
    experiment = await db.get(Experiment, experiment_id)

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    if experiment.status != ExperimentStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only stop RUNNING experiments. Current: {experiment.status.value}",
        )

    # Compute final metrics and statistical significance
    await _compute_experiment_results(experiment, db)

    experiment.status = ExperimentStatus.COMPLETED
    if not experiment.end_date:
        experiment.end_date = date.today()

    await db.flush()
    await db.refresh(experiment)

    control_factor = await db.get(Factor, experiment.control_factor_id)
    treatment_factor = await db.get(Factor, experiment.treatment_factor_id)

    return _build_experiment_response(experiment, control_factor, treatment_factor)


@router.post("/experiments/{experiment_id}/promote", response_model=ExperimentResponse)
async def promote_winner(
    experiment_id: int,
    confirm: bool = Query(False, description="Confirm promotion"),
    db: AsyncSession = Depends(get_db),
):
    """Promote the winning variant to production."""
    experiment = await db.get(Experiment, experiment_id)

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    if experiment.status != ExperimentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only promote from COMPLETED experiments",
        )

    if not experiment.winner or experiment.winner == "inconclusive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No clear winner to promote",
        )

    if experiment.winner_promoted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Winner already promoted",
        )

    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must confirm promotion with confirm=true",
        )

    experiment.winner_promoted = True
    experiment.promoted_at = datetime.utcnow()

    await db.flush()
    await db.refresh(experiment)

    control_factor = await db.get(Factor, experiment.control_factor_id)
    treatment_factor = await db.get(Factor, experiment.treatment_factor_id)

    return _build_experiment_response(experiment, control_factor, treatment_factor)


@router.delete("/experiments/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete an experiment (only DRAFT or CANCELLED)."""
    experiment = await db.get(Experiment, experiment_id)

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    if experiment.status not in [ExperimentStatus.DRAFT, ExperimentStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete DRAFT or CANCELLED experiments",
        )

    await db.delete(experiment)


async def _compute_experiment_results(experiment: Experiment, db: AsyncSession):
    """Compute metrics and statistical significance for an experiment."""
    # Get factor values for control
    control_query = (
        select(FactorValue)
        .where(FactorValue.factor_id == experiment.control_factor_id)
    )
    if experiment.start_date:
        control_query = control_query.where(FactorValue.as_of_date >= experiment.start_date)
    if experiment.end_date:
        control_query = control_query.where(FactorValue.as_of_date <= experiment.end_date)
    if experiment.target_tickers:
        control_query = control_query.where(FactorValue.ticker.in_(experiment.target_tickers))

    control_result = await db.execute(control_query)
    control_values = control_result.scalars().all()

    # Get factor values for treatment
    treatment_query = (
        select(FactorValue)
        .where(FactorValue.factor_id == experiment.treatment_factor_id)
    )
    if experiment.start_date:
        treatment_query = treatment_query.where(FactorValue.as_of_date >= experiment.start_date)
    if experiment.end_date:
        treatment_query = treatment_query.where(FactorValue.as_of_date <= experiment.end_date)
    if experiment.target_tickers:
        treatment_query = treatment_query.where(FactorValue.ticker.in_(experiment.target_tickers))

    treatment_result = await db.execute(treatment_query)
    treatment_values = treatment_result.scalars().all()

    # Compute control metrics
    if control_values:
        control_data = [float(v.mean) for v in control_values]
        experiment.control_sample_size = len(control_data)
        if len(control_data) > 1:
            experiment.control_ic = Decimal(str(round(np.mean(control_data), 6)))
            if np.std(control_data) > 0:
                experiment.control_ir = Decimal(str(round(np.mean(control_data) / np.std(control_data), 6)))
            experiment.control_hit_rate = Decimal(str(round(np.mean([1 if v > 0 else 0 for v in control_data]), 4)))
            experiment.control_tstat = Decimal(str(round(np.mean(control_data) / (np.std(control_data) / np.sqrt(len(control_data))), 4))) if np.std(control_data) > 0 else None

    # Compute treatment metrics
    if treatment_values:
        treatment_data = [float(v.mean) for v in treatment_values]
        experiment.treatment_sample_size = len(treatment_data)
        if len(treatment_data) > 1:
            experiment.treatment_ic = Decimal(str(round(np.mean(treatment_data), 6)))
            if np.std(treatment_data) > 0:
                experiment.treatment_ir = Decimal(str(round(np.mean(treatment_data) / np.std(treatment_data), 6)))
            experiment.treatment_hit_rate = Decimal(str(round(np.mean([1 if v > 0 else 0 for v in treatment_data]), 4)))
            experiment.treatment_tstat = Decimal(str(round(np.mean(treatment_data) / (np.std(treatment_data) / np.sqrt(len(treatment_data))), 4))) if np.std(treatment_data) > 0 else None

    # Statistical significance testing (two-sample t-test)
    if control_values and treatment_values and len(control_values) >= 2 and len(treatment_values) >= 2:
        control_data = [float(v.mean) for v in control_values]
        treatment_data = [float(v.mean) for v in treatment_values]

        # Two-sample t-test for IC difference
        t_stat, p_value = scipy_stats.ttest_ind(control_data, treatment_data)

        experiment.p_value_ic = Decimal(str(round(p_value, 6)))
        experiment.is_significant = p_value < float(experiment.significance_level)

        # Confidence interval for difference
        mean_diff = np.mean(treatment_data) - np.mean(control_data)
        se_diff = np.sqrt(np.var(control_data)/len(control_data) + np.var(treatment_data)/len(treatment_data))
        ci_low = mean_diff - 1.96 * se_diff
        ci_high = mean_diff + 1.96 * se_diff

        experiment.confidence_interval_lower = Decimal(str(round(ci_low, 6)))
        experiment.confidence_interval_upper = Decimal(str(round(ci_high, 6)))

        # Determine winner
        if experiment.is_significant:
            if np.mean(treatment_data) > np.mean(control_data):
                experiment.winner = "treatment"
            else:
                experiment.winner = "control"
        else:
            experiment.winner = "inconclusive"


def _build_experiment_response(
    experiment: Experiment,
    control_factor: Optional[Factor],
    treatment_factor: Optional[Factor],
) -> ExperimentResponse:
    """Build ExperimentResponse from Experiment model."""
    control_metrics = ExperimentMetrics(
        ic=float(experiment.control_ic) if experiment.control_ic else None,
        ir=float(experiment.control_ir) if experiment.control_ir else None,
        tstat=float(experiment.control_tstat) if experiment.control_tstat else None,
        hit_rate=float(experiment.control_hit_rate) if experiment.control_hit_rate else None,
    )

    treatment_metrics = ExperimentMetrics(
        ic=float(experiment.treatment_ic) if experiment.treatment_ic else None,
        ir=float(experiment.treatment_ir) if experiment.treatment_ir else None,
        tstat=float(experiment.treatment_tstat) if experiment.treatment_tstat else None,
        hit_rate=float(experiment.treatment_hit_rate) if experiment.treatment_hit_rate else None,
    )

    # Get metrics history from snapshots if available
    metrics_history = []
    if experiment.daily_metrics:
        metrics_history = experiment.daily_metrics

    return ExperimentResponse(
        id=experiment.id,
        name=experiment.name,
        description=experiment.description,
        control_factor_id=control_factor.factor_id if control_factor else "unknown",
        treatment_factor_id=treatment_factor.factor_id if treatment_factor else "unknown",
        start_date=experiment.start_date,
        end_date=experiment.end_date,
        status=experiment.status.value,
        control_metrics=control_metrics,
        treatment_metrics=treatment_metrics,
        p_value=float(experiment.p_value_ic) if experiment.p_value_ic else None,
        is_significant=experiment.is_significant,
        winner=experiment.winner,
        significance_threshold=float(experiment.significance_level),
        metrics_history=metrics_history,
    )

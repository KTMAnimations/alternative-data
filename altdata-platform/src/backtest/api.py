"""API endpoints for backtesting."""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.database import get_db
from .engine import BacktestEngine, BacktestJobManager, job_manager

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


# Request/Response Models

class BacktestRequest(BaseModel):
    """Request model for running a backtest."""
    factor_name: str = Field(..., min_length=1, max_length=100)
    universe: List[str] = Field(..., min_items=2, max_items=500)
    start_date: date
    end_date: date
    rebalance_freq: str = Field("daily", pattern="^(daily|weekly|monthly)$")
    long_short: bool = True
    top_n: int = Field(10, ge=1, le=100)
    transaction_cost: float = Field(0.001, ge=0, le=0.1)


class BacktestJobResponse(BaseModel):
    """Response model for submitted backtest job."""
    job_id: str
    status: str


class BacktestMetricsResponse(BaseModel):
    """Response model for backtest metrics."""
    job_id: str
    status: str
    factor_name: Optional[str] = None
    universe_size: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    rebalance_freq: Optional[str] = None
    long_short: Optional[bool] = None
    top_n: Optional[int] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    total_return: Optional[float] = None
    annualized_return: Optional[float] = None
    volatility: Optional[float] = None
    ic_mean: Optional[float] = None
    ic_ir: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    turnover: Optional[float] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class BacktestTimeSeriesResponse(BaseModel):
    """Response model for backtest time series data."""
    job_id: str
    dates: List[str]
    cumulative_returns: List[float]
    daily_returns: List[float]


class BacktestPositionsResponse(BaseModel):
    """Response model for backtest positions."""
    job_id: str
    dates: List[str]
    positions: dict  # entity_id -> list of weights


class BacktestICResponse(BaseModel):
    """Response model for IC series."""
    job_id: str
    dates: List[str]
    ic_values: List[float]
    ic_mean: float
    ic_ir: float


# Endpoints

@router.post("/run", response_model=BacktestJobResponse, status_code=202)
def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Submit a backtest job.

    The backtest runs asynchronously. Use the returned job_id to check status
    and retrieve results.
    """
    # Validate dates
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before end_date"
        )

    # Validate date range (max 5 years)
    date_diff = (request.end_date - request.start_date).days
    if date_diff > 365 * 5:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 5 years"
        )

    # Submit job
    job_id = job_manager.submit_job(
        factor_name=request.factor_name,
        universe=request.universe,
        start_date=request.start_date,
        end_date=request.end_date,
        rebalance_freq=request.rebalance_freq,
        long_short=request.long_short,
        top_n=request.top_n,
        transaction_cost=request.transaction_cost,
    )

    return BacktestJobResponse(job_id=job_id, status="running")


@router.get("/results/{job_id}", response_model=BacktestMetricsResponse)
def get_backtest_results(job_id: str):
    """Get backtest results by job ID."""
    job_status = job_manager.get_job_status(job_id)

    if job_status is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_status["status"] == "running":
        return BacktestMetricsResponse(job_id=job_id, status="running")

    if job_status["status"] == "failed":
        return BacktestMetricsResponse(
            job_id=job_id,
            status="failed",
            error=job_status.get("error"),
        )

    result = job_manager.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Results not found")

    return BacktestMetricsResponse(**result.to_dict())


@router.get("/results/{job_id}/timeseries", response_model=BacktestTimeSeriesResponse)
def get_backtest_timeseries(job_id: str):
    """Get backtest time series data (returns)."""
    job_status = job_manager.get_job_status(job_id)

    if job_status is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_status["status"] != "complete":
        raise HTTPException(
            status_code=400,
            detail=f"Job status is {job_status['status']}, not complete"
        )

    result = job_manager.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Results not found")

    return BacktestTimeSeriesResponse(
        job_id=job_id,
        dates=[d.isoformat() for d in result.cumulative_returns.index],
        cumulative_returns=result.cumulative_returns.tolist(),
        daily_returns=result.returns.tolist(),
    )


@router.get("/results/{job_id}/positions", response_model=BacktestPositionsResponse)
def get_backtest_positions(job_id: str):
    """Get backtest position history."""
    job_status = job_manager.get_job_status(job_id)

    if job_status is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_status["status"] != "complete":
        raise HTTPException(
            status_code=400,
            detail=f"Job status is {job_status['status']}, not complete"
        )

    result = job_manager.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Results not found")

    positions_dict = {}
    for col in result.positions.columns:
        positions_dict[col] = result.positions[col].tolist()

    return BacktestPositionsResponse(
        job_id=job_id,
        dates=[d.isoformat() for d in result.positions.index],
        positions=positions_dict,
    )


@router.get("/results/{job_id}/ic", response_model=BacktestICResponse)
def get_backtest_ic(job_id: str):
    """Get Information Coefficient series."""
    job_status = job_manager.get_job_status(job_id)

    if job_status is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_status["status"] != "complete":
        raise HTTPException(
            status_code=400,
            detail=f"Job status is {job_status['status']}, not complete"
        )

    result = job_manager.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Results not found")

    return BacktestICResponse(
        job_id=job_id,
        dates=[d.isoformat() for d in result.ic_series.index],
        ic_values=result.ic_series.tolist(),
        ic_mean=result.ic_mean,
        ic_ir=result.ic_ir,
    )


@router.get("/jobs")
def list_jobs(
    status: Optional[str] = Query(None, pattern="^(running|complete|failed)$"),
    limit: int = Query(50, ge=1, le=100),
):
    """List recent backtest jobs."""
    jobs = []

    for job_id, job_data in job_manager._jobs.items():
        if status and job_data["status"] != status:
            continue

        jobs.append({
            "job_id": job_id,
            "status": job_data["status"],
            "factor_name": job_data.get("factor_name"),
            "submitted_at": job_data.get("submitted_at", "").isoformat() if job_data.get("submitted_at") else None,
        })

    # Sort by submitted_at descending
    jobs.sort(
        key=lambda x: x.get("submitted_at") or "",
        reverse=True
    )

    return {"jobs": jobs[:limit], "total": len(jobs)}


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    """Delete a backtest job and its results."""
    if job_id not in job_manager._jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    del job_manager._jobs[job_id]

    if job_id in job_manager._results:
        del job_manager._results[job_id]


@router.post("/quick")
def run_quick_backtest(
    request: BacktestRequest,
    db: Session = Depends(get_db),
):
    """Run a backtest synchronously and return results immediately.

    Use this for small backtests. For larger backtests, use /run.
    """
    # Validate dates
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before end_date"
        )

    # Limit date range for quick backtests
    date_diff = (request.end_date - request.start_date).days
    if date_diff > 365:
        raise HTTPException(
            status_code=400,
            detail="Quick backtest date range limited to 1 year. Use /run for longer periods."
        )

    if len(request.universe) > 50:
        raise HTTPException(
            status_code=400,
            detail="Quick backtest limited to 50 entities. Use /run for larger universes."
        )

    try:
        engine = BacktestEngine(request.start_date, request.end_date, session=db)
        result = engine.run(
            factor_name=request.factor_name,
            universe=request.universe,
            rebalance_freq=request.rebalance_freq,
            long_short=request.long_short,
            top_n=request.top_n,
            transaction_cost=request.transaction_cost,
        )

        return result.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

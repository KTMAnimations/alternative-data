"""Backtesting engine for factor evaluation."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import math
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from src.models.database import SessionLocal


def _safe_round(value: float, decimals: int = 4) -> Optional[float]:
    """Safely round a float value, handling NaN and Infinity.

    Args:
        value: The value to round.
        decimals: Number of decimal places.

    Returns:
        Rounded value, or None if value is NaN or Infinity.
    """
    if value is None or math.isnan(value) or math.isinf(value):
        return None
    return round(value, decimals)
from src.models.schemas import Factor
from .metrics import (
    calculate_sharpe,
    calculate_max_drawdown,
    calculate_ic,
    calculate_ic_series,
    calculate_ic_ir,
    calculate_turnover,
    calculate_sortino,
    calculate_calmar,
    calculate_win_rate,
    calculate_profit_factor,
)
from .prices import PriceProvider

logger = logging.getLogger(__name__)


class RebalanceFrequency(str, Enum):
    """Rebalance frequency options."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class BacktestResult:
    """Container for backtest results."""

    # Core metrics
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    annualized_return: float
    volatility: float

    # IC metrics
    ic_mean: float
    ic_ir: float

    # Additional metrics
    sortino_ratio: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    turnover: float

    # Time series data
    returns: pd.Series = field(repr=False)
    cumulative_returns: pd.Series = field(repr=False)
    factor_values: pd.DataFrame = field(repr=False)
    positions: pd.DataFrame = field(repr=False)
    ic_series: pd.Series = field(repr=False)

    # Metadata
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    factor_name: str = ""
    universe: List[str] = field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    rebalance_freq: str = "daily"
    long_short: bool = True
    top_n: int = 10
    completed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "job_id": self.job_id,
            "status": "complete",
            "factor_name": self.factor_name,
            "universe_size": len(self.universe),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "rebalance_freq": self.rebalance_freq,
            "long_short": self.long_short,
            "top_n": self.top_n,
            "sharpe_ratio": _safe_round(self.sharpe_ratio),
            "sortino_ratio": _safe_round(self.sortino_ratio),
            "calmar_ratio": _safe_round(self.calmar_ratio),
            "max_drawdown": _safe_round(self.max_drawdown),
            "total_return": _safe_round(self.total_return),
            "annualized_return": _safe_round(self.annualized_return),
            "volatility": _safe_round(self.volatility),
            "ic_mean": _safe_round(self.ic_mean),
            "ic_ir": _safe_round(self.ic_ir),
            "win_rate": _safe_round(self.win_rate),
            "profit_factor": _safe_round(self.profit_factor),
            "turnover": _safe_round(self.turnover),
            "completed_at": self.completed_at.isoformat(),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
            "ic_mean": self.ic_mean,
            "turnover": self.turnover,
        }


class BacktestEngine:
    """Engine for running factor backtests."""

    def __init__(
        self,
        start_date: date,
        end_date: date,
        session: Optional[Session] = None,
        price_provider: Optional[PriceProvider] = None,
    ):
        """Initialize backtest engine.

        Args:
            start_date: Backtest start date.
            end_date: Backtest end date.
            session: SQLAlchemy session for factor data.
            price_provider: Provider for price data.
        """
        self.start_date = start_date
        self.end_date = end_date
        self._session = session
        self._owns_session = session is None
        self.price_provider = price_provider or PriceProvider()

    def _get_session(self) -> Session:
        """Get or create database session."""
        if self._session is None:
            self._session = SessionLocal()
        return self._session

    def close(self):
        """Close session if we own it."""
        if self._owns_session and self._session:
            self._session.close()
            self._session = None

    def run(
        self,
        factor_name: str,
        universe: List[str],
        rebalance_freq: str = "daily",
        long_short: bool = True,
        top_n: int = 10,
        transaction_cost: float = 0.001,
    ) -> BacktestResult:
        """Run factor backtest.

        Args:
            factor_name: Name of the factor to backtest.
            universe: List of entity IDs (tickers).
            rebalance_freq: Rebalancing frequency ('daily', 'weekly', 'monthly').
            long_short: Whether to run long-short strategy.
            top_n: Number of positions on each side.
            transaction_cost: Transaction cost per trade (fraction).

        Returns:
            BacktestResult with all metrics and time series.
        """
        logger.info(f"Running backtest for {factor_name} on {len(universe)} entities")

        # Get factor values
        factor_df = self._get_factor_data(factor_name, universe)

        if factor_df.empty:
            raise ValueError(f"No factor data found for {factor_name}")

        # Get price returns
        returns_df = self.price_provider.get_returns(
            universe, self.start_date, self.end_date
        )

        if returns_df.empty:
            raise ValueError("No price data available for universe")

        # Get forward returns for IC calculation
        forward_returns_df = self.price_provider.get_forward_returns(
            universe, self.start_date, self.end_date, forward_days=1
        )

        # Generate rebalance dates
        rebalance_dates = self._get_rebalance_dates(factor_df.index, rebalance_freq)

        # Build positions
        positions = self._build_positions(
            factor_df, rebalance_dates, long_short, top_n
        )

        # Calculate strategy returns
        strategy_returns = self._calculate_strategy_returns(
            positions, returns_df, transaction_cost
        )

        # Calculate cumulative returns
        cumulative_returns = (1 + strategy_returns).cumprod()

        # Calculate IC series
        ic_series = calculate_ic_series(factor_df, forward_returns_df)

        # Calculate all metrics
        sharpe = calculate_sharpe(strategy_returns)
        max_dd = calculate_max_drawdown(cumulative_returns)
        total_return = float(cumulative_returns.iloc[-1] - 1) if not cumulative_returns.empty else 0.0

        # Annualized return
        n_years = (self.end_date - self.start_date).days / 365.25
        annualized_return = float((1 + total_return) ** (1 / n_years) - 1) if n_years > 0 else 0.0

        # Volatility
        volatility = float(strategy_returns.std() * np.sqrt(252)) if not strategy_returns.empty else 0.0

        # IC metrics
        ic_mean = float(ic_series.mean()) if not ic_series.empty else 0.0
        ic_ir = calculate_ic_ir(ic_series)

        # Additional metrics
        sortino = calculate_sortino(strategy_returns)
        calmar = calculate_calmar(strategy_returns, max_dd)
        win_rate = calculate_win_rate(strategy_returns)
        profit_factor = calculate_profit_factor(strategy_returns)
        turnover = calculate_turnover(positions)

        return BacktestResult(
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            ic_mean=ic_mean,
            ic_ir=ic_ir,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            win_rate=win_rate,
            profit_factor=profit_factor,
            turnover=turnover,
            returns=strategy_returns,
            cumulative_returns=cumulative_returns,
            factor_values=factor_df,
            positions=positions,
            ic_series=ic_series,
            factor_name=factor_name,
            universe=universe,
            start_date=self.start_date,
            end_date=self.end_date,
            rebalance_freq=rebalance_freq,
            long_short=long_short,
            top_n=top_n,
        )

    def _get_factor_data(
        self, factor_name: str, universe: List[str]
    ) -> pd.DataFrame:
        """Get factor values as DataFrame.

        Args:
            factor_name: Factor name.
            universe: List of entity IDs.

        Returns:
            DataFrame with index=dates, columns=entity_ids.
        """
        session = self._get_session()

        factors = (
            session.query(Factor)
            .filter(
                Factor.factor_name == factor_name,
                Factor.entity_id.in_(universe),
                Factor.effective_date >= self.start_date,
                Factor.effective_date <= self.end_date,
                Factor.value.isnot(None),
            )
            .all()
        )

        if not factors:
            return pd.DataFrame()

        # Convert to DataFrame
        data = []
        for f in factors:
            data.append({
                'date': f.effective_date,
                'entity_id': f.entity_id,
                'value': f.value,
            })

        df = pd.DataFrame(data)

        # Pivot to get entity columns
        factor_df = df.pivot(index='date', columns='entity_id', values='value')
        factor_df.index = pd.to_datetime(factor_df.index)
        factor_df = factor_df.sort_index()

        return factor_df

    def _get_rebalance_dates(
        self, dates: pd.DatetimeIndex, freq: str
    ) -> List[pd.Timestamp]:
        """Get rebalance dates based on frequency.

        Args:
            dates: Available dates.
            freq: Rebalance frequency.

        Returns:
            List of rebalance dates.
        """
        if freq == "daily":
            return list(dates)

        elif freq == "weekly":
            # Rebalance on Mondays (or first available day of week)
            rebalance_dates = []
            current_week = None

            for d in sorted(dates):
                week = d.isocalendar()[1]
                if week != current_week:
                    rebalance_dates.append(d)
                    current_week = week

            return rebalance_dates

        elif freq == "monthly":
            # Rebalance on first day of each month
            rebalance_dates = []
            current_month = None

            for d in sorted(dates):
                month = (d.year, d.month)
                if month != current_month:
                    rebalance_dates.append(d)
                    current_month = month

            return rebalance_dates

        else:
            raise ValueError(f"Unknown rebalance frequency: {freq}")

    def _build_positions(
        self,
        factor_df: pd.DataFrame,
        rebalance_dates: List[pd.Timestamp],
        long_short: bool,
        top_n: int,
    ) -> pd.DataFrame:
        """Build position weights based on factor rankings.

        Args:
            factor_df: Factor values DataFrame.
            rebalance_dates: Dates to rebalance.
            long_short: Whether to use long-short strategy.
            top_n: Number of positions per side.

        Returns:
            DataFrame of position weights.
        """
        positions = pd.DataFrame(
            0.0, index=factor_df.index, columns=factor_df.columns
        )

        current_weights = pd.Series(0.0, index=factor_df.columns)

        for dt in factor_df.index:
            if dt in rebalance_dates:
                # Get factor values for this date
                values = factor_df.loc[dt].dropna()

                if len(values) < top_n:
                    # Not enough data
                    current_weights = pd.Series(0.0, index=factor_df.columns)
                else:
                    # Rank entities
                    ranked = values.rank(ascending=False)

                    if long_short:
                        # Long top_n, short bottom_n
                        n_positions = min(top_n, len(values) // 2)

                        long_entities = ranked.nsmallest(n_positions).index
                        short_entities = ranked.nlargest(n_positions).index

                        weights = pd.Series(0.0, index=factor_df.columns)
                        weights[long_entities] = 1.0 / n_positions
                        weights[short_entities] = -1.0 / n_positions

                        current_weights = weights
                    else:
                        # Long only top_n
                        n_positions = min(top_n, len(values))
                        long_entities = ranked.nsmallest(n_positions).index

                        weights = pd.Series(0.0, index=factor_df.columns)
                        weights[long_entities] = 1.0 / n_positions

                        current_weights = weights

            positions.loc[dt] = current_weights

        return positions

    def _calculate_strategy_returns(
        self,
        positions: pd.DataFrame,
        returns_df: pd.DataFrame,
        transaction_cost: float,
    ) -> pd.Series:
        """Calculate strategy returns.

        Args:
            positions: Position weights.
            returns_df: Asset returns.
            transaction_cost: Cost per trade.

        Returns:
            Series of strategy returns.
        """
        # Align dataframes
        common_dates = positions.index.intersection(returns_df.index)
        common_entities = positions.columns.intersection(returns_df.columns)

        if len(common_dates) == 0 or len(common_entities) == 0:
            return pd.Series(dtype=float)

        positions_aligned = positions.loc[common_dates, common_entities]
        returns_aligned = returns_df.loc[common_dates, common_entities]

        # Calculate raw returns (position * return)
        strategy_returns = (positions_aligned.shift(1) * returns_aligned).sum(axis=1)

        # Apply transaction costs
        position_changes = positions_aligned.diff().abs()
        costs = position_changes.sum(axis=1) * transaction_cost

        strategy_returns = strategy_returns - costs

        # Drop first row (no prior position)
        strategy_returns = strategy_returns.iloc[1:]

        return strategy_returns


class BacktestJobManager:
    """Manager for async backtest jobs."""

    def __init__(self):
        """Initialize job manager."""
        self._jobs: Dict[str, Dict] = {}
        self._results: Dict[str, BacktestResult] = {}

    def submit_job(
        self,
        factor_name: str,
        universe: List[str],
        start_date: date,
        end_date: date,
        rebalance_freq: str = "daily",
        long_short: bool = True,
        top_n: int = 10,
        transaction_cost: float = 0.001,
    ) -> str:
        """Submit a backtest job.

        Args:
            factor_name: Factor to backtest.
            universe: List of entity IDs.
            start_date: Start date.
            end_date: End date.
            rebalance_freq: Rebalance frequency.
            long_short: Long-short strategy.
            top_n: Number of positions.
            transaction_cost: Transaction cost per trade (fraction).

        Returns:
            Job ID.
        """
        job_id = str(uuid.uuid4())

        self._jobs[job_id] = {
            "status": "running",
            "factor_name": factor_name,
            "universe": universe,
            "start_date": start_date,
            "end_date": end_date,
            "rebalance_freq": rebalance_freq,
            "long_short": long_short,
            "top_n": top_n,
            "transaction_cost": transaction_cost,
            "submitted_at": datetime.utcnow(),
        }

        # Run backtest synchronously for now
        # In production, this would be async (Celery, etc.)
        try:
            engine = BacktestEngine(start_date, end_date)
            result = engine.run(
                factor_name=factor_name,
                universe=universe,
                rebalance_freq=rebalance_freq,
                long_short=long_short,
                top_n=top_n,
                transaction_cost=transaction_cost,
            )
            result.job_id = job_id

            self._results[job_id] = result
            self._jobs[job_id]["status"] = "complete"

            engine.close()

        except Exception as e:
            self._jobs[job_id]["status"] = "failed"
            self._jobs[job_id]["error"] = str(e)
            logger.error(f"Backtest job {job_id} failed: {e}")

        return job_id

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get job status."""
        return self._jobs.get(job_id)

    def get_result(self, job_id: str) -> Optional[BacktestResult]:
        """Get backtest result."""
        return self._results.get(job_id)


# Global job manager instance
job_manager = BacktestJobManager()

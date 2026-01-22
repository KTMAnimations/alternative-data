"""Backtest performance metrics."""

import numpy as np
import pandas as pd
from typing import Optional


def calculate_sharpe(
    returns: pd.Series,
    risk_free: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """Calculate annualized Sharpe ratio.

    Args:
        returns: Daily returns series.
        risk_free: Annual risk-free rate (default 0).
        periods_per_year: Number of trading periods per year (default 252 for daily).

    Returns:
        Annualized Sharpe ratio.
    """
    if returns.empty:
        return 0.0

    std = returns.std()
    if std == 0 or std < 1e-10:
        return 0.0

    excess_returns = returns - (risk_free / periods_per_year)
    return float(np.sqrt(periods_per_year) * excess_returns.mean() / excess_returns.std())


def calculate_max_drawdown(cumulative_returns: pd.Series) -> float:
    """Calculate maximum drawdown.

    Args:
        cumulative_returns: Cumulative returns series (1 = starting value).

    Returns:
        Maximum drawdown as a negative percentage (e.g., -0.15 for 15% drawdown).
    """
    if cumulative_returns.empty:
        return 0.0

    # Calculate running maximum
    running_max = cumulative_returns.expanding().max()

    # Calculate drawdown
    drawdown = (cumulative_returns - running_max) / running_max

    return float(drawdown.min())


def calculate_ic(
    factor_values: pd.Series,
    forward_returns: pd.Series,
    method: str = "spearman"
) -> Optional[float]:
    """Calculate Information Coefficient (rank correlation between factor and returns).

    Args:
        factor_values: Factor values series.
        forward_returns: Forward returns series (aligned with factor values).
        method: Correlation method ('spearman' or 'pearson').

    Returns:
        IC value or None if insufficient data.
    """
    if len(factor_values) < 5 or len(forward_returns) < 5:
        return None

    # Align and drop NaN
    aligned = pd.DataFrame({
        'factor': factor_values,
        'returns': forward_returns
    }).dropna()

    if len(aligned) < 5:
        return None

    return float(aligned['factor'].corr(aligned['returns'], method=method))


def calculate_ic_series(
    factor_df: pd.DataFrame,
    returns_df: pd.DataFrame,
    method: str = "spearman"
) -> pd.Series:
    """Calculate IC series over time.

    Args:
        factor_df: DataFrame with factor values (index=dates, columns=entities).
        returns_df: DataFrame with forward returns (aligned with factor_df).
        method: Correlation method.

    Returns:
        Series of IC values indexed by date.
    """
    ic_values = {}

    for date in factor_df.index:
        if date not in returns_df.index:
            continue

        factors = factor_df.loc[date].dropna()
        returns = returns_df.loc[date].dropna()

        # Get common entities
        common = factors.index.intersection(returns.index)
        if len(common) < 5:
            continue

        ic = calculate_ic(factors[common], returns[common], method)
        if ic is not None:
            ic_values[date] = ic

    return pd.Series(ic_values)


def calculate_ic_ir(ic_series: pd.Series) -> float:
    """Calculate IC Information Ratio (mean IC / std IC).

    Args:
        ic_series: Series of IC values.

    Returns:
        IC Information Ratio.
    """
    if ic_series.empty:
        return 0.0

    std = ic_series.std()
    if std == 0 or std < 1e-10:
        return 0.0

    return float(ic_series.mean() / std)


def calculate_turnover(positions: pd.DataFrame) -> float:
    """Calculate average turnover.

    Args:
        positions: DataFrame with positions (index=dates, columns=entities).

    Returns:
        Average daily turnover as a fraction.
    """
    if positions.empty or len(positions) < 2:
        return 0.0

    # Fill NaN with 0 (no position)
    positions = positions.fillna(0)

    # Calculate absolute changes in positions
    position_changes = positions.diff().abs()

    # Sum across entities for each date
    daily_turnover = position_changes.sum(axis=1)

    # Average turnover (excluding first row which is all NaN)
    return float(daily_turnover.iloc[1:].mean())


def calculate_sortino(
    returns: pd.Series,
    risk_free: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """Calculate annualized Sortino ratio (downside risk only).

    Args:
        returns: Daily returns series.
        risk_free: Annual risk-free rate.
        periods_per_year: Number of trading periods per year.

    Returns:
        Annualized Sortino ratio.
    """
    if returns.empty:
        return 0.0

    excess_returns = returns - (risk_free / periods_per_year)
    downside_returns = excess_returns[excess_returns < 0]

    if downside_returns.empty or downside_returns.std() == 0:
        return float('inf') if excess_returns.mean() > 0 else 0.0

    downside_std = downside_returns.std()
    return float(np.sqrt(periods_per_year) * excess_returns.mean() / downside_std)


def calculate_calmar(
    returns: pd.Series,
    max_drawdown: float,
    periods_per_year: int = 252
) -> float:
    """Calculate Calmar ratio (annualized return / max drawdown).

    Args:
        returns: Daily returns series.
        max_drawdown: Maximum drawdown (negative value).
        periods_per_year: Number of trading periods per year.

    Returns:
        Calmar ratio.
    """
    if returns.empty or max_drawdown == 0:
        return 0.0

    annualized_return = returns.mean() * periods_per_year
    return float(annualized_return / abs(max_drawdown))


def calculate_win_rate(returns: pd.Series) -> float:
    """Calculate win rate (percentage of positive return days).

    Args:
        returns: Daily returns series.

    Returns:
        Win rate as a fraction.
    """
    if returns.empty:
        return 0.0

    return float((returns > 0).sum() / len(returns))


def calculate_profit_factor(returns: pd.Series) -> float:
    """Calculate profit factor (gross profits / gross losses).

    Args:
        returns: Daily returns series.

    Returns:
        Profit factor.
    """
    if returns.empty:
        return 0.0

    gross_profit = returns[returns > 0].sum()
    gross_loss = abs(returns[returns < 0].sum())

    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0

    return float(gross_profit / gross_loss)

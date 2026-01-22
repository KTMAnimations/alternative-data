"""Backtesting example using the AltData SDK.

This example demonstrates how to use factor data for backtesting
trading strategies.
"""

from datetime import date, timedelta
from typing import List

import pandas as pd

from altdata import AltDataClient


def get_factor_data(
    client: AltDataClient,
    factor_name: str,
    tickers: List[str],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Fetch factor data for multiple tickers and combine into a DataFrame."""
    all_data = []

    for ticker in tickers:
        try:
            data = client.get_factor(
                factor_name,
                entity_id=ticker,
                start_date=start_date,
                end_date=end_date,
            )
            df = data.to_dataframe()
            df["ticker"] = ticker
            all_data.append(df.reset_index())
        except Exception as e:
            print(f"Error getting {factor_name} for {ticker}: {e}")

    if not all_data:
        return pd.DataFrame()

    return pd.concat(all_data, ignore_index=True)


def rank_tickers_by_factor(df: pd.DataFrame, ascending: bool = True) -> pd.DataFrame:
    """Rank tickers by factor value for each date."""
    # Pivot to have tickers as columns
    pivot = df.pivot(index="date", columns="ticker", values="value")

    # Rank within each date (1 = best)
    ranks = pivot.rank(axis=1, ascending=ascending)

    return ranks


def simple_backtest(
    factor_ranks: pd.DataFrame,
    prices: pd.DataFrame,
    top_n: int = 3,
    bottom_n: int = 3,
) -> pd.DataFrame:
    """Simple long-short backtest based on factor ranks.

    Args:
        factor_ranks: DataFrame with tickers as columns, dates as index
        prices: DataFrame with tickers as columns, dates as index
        top_n: Number of top-ranked tickers to go long
        bottom_n: Number of bottom-ranked tickers to go short

    Returns:
        DataFrame with backtest results
    """
    # Calculate returns
    returns = prices.pct_change()

    results = []

    for date_idx in range(1, len(factor_ranks)):
        prev_date = factor_ranks.index[date_idx - 1]
        curr_date = factor_ranks.index[date_idx]

        # Get ranks from previous period
        ranks = factor_ranks.loc[prev_date].dropna()
        if len(ranks) < top_n + bottom_n:
            continue

        # Select long and short positions
        sorted_ranks = ranks.sort_values()
        long_tickers = sorted_ranks.head(top_n).index.tolist()
        short_tickers = sorted_ranks.tail(bottom_n).index.tolist()

        # Get current period returns
        if curr_date not in returns.index:
            continue

        period_returns = returns.loc[curr_date]

        # Calculate portfolio return
        long_return = period_returns[long_tickers].mean() if long_tickers else 0
        short_return = period_returns[short_tickers].mean() if short_tickers else 0

        # Long-short return
        portfolio_return = (long_return - short_return) / 2

        results.append(
            {
                "date": curr_date,
                "long_return": long_return,
                "short_return": short_return,
                "portfolio_return": portfolio_return,
                "long_tickers": long_tickers,
                "short_tickers": short_tickers,
            }
        )

    return pd.DataFrame(results)


def calculate_metrics(returns: pd.Series) -> dict:
    """Calculate basic performance metrics."""
    cumulative = (1 + returns).cumprod()

    return {
        "total_return": cumulative.iloc[-1] - 1 if len(cumulative) > 0 else 0,
        "sharpe_ratio": (returns.mean() / returns.std() * (252**0.5))
        if returns.std() > 0
        else 0,
        "max_drawdown": (cumulative / cumulative.cummax() - 1).min(),
        "win_rate": (returns > 0).mean(),
        "avg_return": returns.mean(),
        "volatility": returns.std() * (252**0.5),
    }


def main():
    # Initialize client
    client = AltDataClient(
        api_key="your-api-key",
        base_url="http://localhost:8000",
    )

    # Define universe
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "WMT"]

    # Define period
    end_date = date.today()
    start_date = end_date - timedelta(days=180)

    print("=== Fetching Factor Data ===")
    factor_df = get_factor_data(
        client,
        "insider_transaction_momentum",
        tickers,
        start_date,
        end_date,
    )

    if factor_df.empty:
        print("No factor data available")
        return

    print(f"Got {len(factor_df)} factor observations")
    print()

    # Rank tickers
    print("=== Ranking Tickers ===")
    ranks = rank_tickers_by_factor(factor_df, ascending=False)  # Higher = better
    print(ranks.tail())
    print()

    # For a real backtest, you would fetch price data here
    # This example shows the structure - you would use yfinance or similar
    print("=== Backtest Results ===")
    print("To run a full backtest, you would need historical price data.")
    print("You can fetch prices using yfinance:")
    print()
    print("  import yfinance as yf")
    print("  prices = yf.download(tickers, start=start_date, end=end_date)['Adj Close']")
    print()
    print("Then run:")
    print("  results = simple_backtest(ranks, prices)")
    print("  metrics = calculate_metrics(results['portfolio_return'])")
    print()

    # List available factor categories for backtesting
    print("=== Available Factor Categories ===")
    categories = client.list_categories()
    for cat in categories.categories:
        print(f"  - {cat.name}: {cat.count} factors")
    print()

    client.close()
    print("Done!")


if __name__ == "__main__":
    main()

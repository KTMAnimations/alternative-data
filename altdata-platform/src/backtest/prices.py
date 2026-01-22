"""Price data provider for backtesting."""

import logging
from datetime import date, timedelta
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class PriceProvider:
    """Fetch historical prices for return calculation."""

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize price provider.

        Args:
            cache_dir: Optional directory to cache price data.
        """
        self.cache_dir = cache_dir
        self._cache: dict = {}

    def get_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date,
        price_type: str = "adj_close"
    ) -> pd.DataFrame:
        """Get historical prices for multiple tickers.

        Args:
            tickers: List of ticker symbols.
            start_date: Start date for price data.
            end_date: End date for price data.
            price_type: Type of price ('close', 'adj_close', 'open', 'high', 'low').

        Returns:
            DataFrame with columns = tickers, index = dates.
        """
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("yfinance is required for price data. Install with: pip install yfinance")

        # Create cache key
        cache_key = (tuple(sorted(tickers)), start_date, end_date, price_type)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Add buffer for forward returns calculation
        buffer_start = start_date - timedelta(days=10)

        try:
            # Download data
            data = yf.download(
                tickers,
                start=buffer_start.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                progress=False,
                auto_adjust=price_type == "adj_close"
            )

            # Handle single ticker case
            if len(tickers) == 1:
                price_col = "Close" if price_type in ("close", "adj_close") else price_type.capitalize()
                if price_col in data.columns:
                    prices = data[[price_col]]
                    prices.columns = tickers
                else:
                    prices = pd.DataFrame(index=data.index, columns=tickers)
            else:
                price_col = "Close" if price_type in ("close", "adj_close") else price_type.capitalize()
                if price_col in data.columns.get_level_values(0):
                    prices = data[price_col]
                else:
                    prices = pd.DataFrame(index=data.index, columns=tickers)

            # Ensure datetime index
            prices.index = pd.to_datetime(prices.index)

            # Cache result
            self._cache[cache_key] = prices

            return prices

        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return pd.DataFrame(columns=tickers)

    def get_returns(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date,
        periods: int = 1
    ) -> pd.DataFrame:
        """Get daily returns.

        Args:
            tickers: List of ticker symbols.
            start_date: Start date.
            end_date: End date.
            periods: Number of periods for return calculation (1 = daily).

        Returns:
            DataFrame of returns.
        """
        prices = self.get_prices(tickers, start_date, end_date)

        if prices.empty:
            return pd.DataFrame(columns=tickers)

        returns = prices.pct_change(periods=periods)

        # Filter to requested date range
        returns = returns[returns.index >= pd.Timestamp(start_date)]
        returns = returns[returns.index <= pd.Timestamp(end_date)]

        return returns

    def get_forward_returns(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date,
        forward_days: int = 1
    ) -> pd.DataFrame:
        """Get forward returns (future returns from each date).

        Args:
            tickers: List of ticker symbols.
            start_date: Start date.
            end_date: End date.
            forward_days: Number of days forward for return calculation.

        Returns:
            DataFrame of forward returns.
        """
        # Get prices with buffer for forward calculation
        extended_end = end_date + timedelta(days=forward_days * 2)
        prices = self.get_prices(tickers, start_date, extended_end)

        if prices.empty:
            return pd.DataFrame(columns=tickers)

        # Calculate forward returns (shift prices back to align with signal date)
        forward_returns = prices.pct_change(periods=forward_days).shift(-forward_days)

        # Filter to requested date range
        forward_returns = forward_returns[forward_returns.index >= pd.Timestamp(start_date)]
        forward_returns = forward_returns[forward_returns.index <= pd.Timestamp(end_date)]

        return forward_returns

    def clear_cache(self):
        """Clear the price cache."""
        self._cache.clear()


class CachedPriceProvider(PriceProvider):
    """Price provider with file-based caching."""

    def __init__(self, cache_dir: str):
        """Initialize with cache directory.

        Args:
            cache_dir: Directory to store cached price data.
        """
        super().__init__(cache_dir)
        self.cache_dir = cache_dir

    def _get_cache_path(self, ticker: str) -> str:
        """Get cache file path for a ticker."""
        import os
        return os.path.join(self.cache_dir, f"{ticker}.parquet")

    def get_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date,
        price_type: str = "adj_close"
    ) -> pd.DataFrame:
        """Get prices with file caching."""
        import os

        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        all_prices = {}

        for ticker in tickers:
            cache_path = self._get_cache_path(ticker)

            if os.path.exists(cache_path):
                # Load from cache
                cached = pd.read_parquet(cache_path)

                # Check if we need to update
                cache_end = cached.index.max().date() if not cached.empty else date.min

                if cache_end >= end_date:
                    # Cache is sufficient
                    all_prices[ticker] = cached[price_type]
                    continue

            # Fetch fresh data
            single_prices = super().get_prices([ticker], start_date, end_date, price_type)

            if not single_prices.empty and ticker in single_prices.columns:
                # Save to cache
                single_prices.to_parquet(cache_path)
                all_prices[ticker] = single_prices[ticker]

        if not all_prices:
            return pd.DataFrame(columns=tickers)

        return pd.DataFrame(all_prices)

"""Box office factors for entertainment company analysis."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_session
from src.entity_mapping.studio_ticker_mapping import PRIMARY_TICKERS, TICKER_TO_STUDIO
from src.models.data_sources import BoxOfficeDaily
from src.transformations.factors.base import BaseFactor, FactorResult


class OpeningWeekendSurprise(BaseFactor):
    """Factor measuring opening weekend performance vs expectations.

    This factor captures the surprise element of a movie's opening weekend
    performance relative to market forecasts. Positive surprise indicates
    better-than-expected performance which may signal strong content and
    positive sentiment for the studio.

    The factor is computed as:
        surprise = (actual_opening - forecast) / forecast

    Since we don't have direct access to forecast data, we use a proxy
    based on theater count and historical averages as the baseline expectation.
    """

    factor_id = "opening_weekend_surprise"
    name = "Opening Weekend Surprise"
    description = "Measures opening weekend box office vs expected performance"
    domain = "entertainment"
    primary_entities = PRIMARY_TICKERS

    # Baseline per-theater average for expectations (in dollars)
    # This is calibrated based on historical industry averages
    BASELINE_PER_THEATER = Decimal("8500")

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute opening weekend surprise factor.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (defaults to primary entities)

        Returns:
            List of FactorResult for each ticker
        """
        if tickers is None:
            tickers = self.primary_entities

        results = []

        async with get_async_session() as session:
            # Look at opening weekends in the trailing 30 days
            lookback_start = as_of_date - timedelta(days=30)

            for ticker in tickers:
                surprise_values = await self._compute_ticker_surprise(
                    session, ticker, lookback_start, as_of_date
                )

                if surprise_values:
                    mean_surprise = sum(surprise_values) / len(surprise_values)
                    variance = self._compute_variance(surprise_values, mean_surprise)

                    results.append(FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal(str(round(mean_surprise, 6))),
                        variance=Decimal(str(round(variance, 6))),
                        data_quality=self._compute_data_quality(len(surprise_values)),
                        metadata={
                            "opening_count": len(surprise_values),
                            "lookback_days": 30,
                        }
                    ))
                else:
                    # No openings - return neutral factor
                    results.append(FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal("0"),
                        variance=Decimal("0.01"),  # Higher uncertainty
                        data_quality=Decimal("0.5"),
                        metadata={"opening_count": 0}
                    ))

        return results

    async def _compute_ticker_surprise(
        self,
        session: AsyncSession,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> list[float]:
        """Compute surprise values for a ticker's opening weekends.

        Args:
            session: Database session
            ticker: Stock ticker
            start_date: Start of lookback period
            end_date: End of lookback period

        Returns:
            List of surprise values (as decimals, e.g., 0.15 for 15%)
        """
        # Query opening weekend data for this studio
        query = select(BoxOfficeDaily).where(
            BoxOfficeDaily.distributor_ticker == ticker,
            BoxOfficeDaily.is_opening_weekend == True,
            BoxOfficeDaily.date >= start_date,
            BoxOfficeDaily.date <= end_date,
        ).order_by(BoxOfficeDaily.date)

        result = await session.execute(query)
        openings = result.scalars().all()

        surprise_values = []
        for opening in openings:
            if opening.theater_count > 0:
                # Expected gross based on theater count and baseline
                expected = self.BASELINE_PER_THEATER * opening.theater_count

                # Actual per-theater performance
                actual = opening.daily_gross

                # Surprise as percentage deviation
                if expected > 0:
                    surprise = float((actual - expected) / expected)
                    # Cap extreme values to reduce noise
                    surprise = max(min(surprise, 5.0), -0.9)
                    surprise_values.append(surprise)

        return surprise_values

    def _compute_variance(self, values: list[float], mean: float) -> float:
        """Compute variance of surprise values."""
        if len(values) < 2:
            return 0.01  # Default variance for single observation
        return sum((v - mean) ** 2 for v in values) / (len(values) - 1)

    def _compute_data_quality(self, opening_count: int) -> Decimal:
        """Compute data quality score based on observation count."""
        if opening_count >= 5:
            return Decimal("1.0")
        elif opening_count >= 3:
            return Decimal("0.9")
        elif opening_count >= 1:
            return Decimal("0.7")
        return Decimal("0.5")

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"S_t = \frac{G_{actual} - G_{expected}}{G_{expected}} = \frac{G_{actual} - (T \times \bar{g})}{T \times \bar{g}}"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return (
            "Opening weekend box office performance is a key indicator of content quality "
            "and audience reception for entertainment companies. Positive surprises "
            "relative to expectations (based on theater count and historical averages) "
            "signal strong content that may drive recurring revenue through theatrical, "
            "streaming, and merchandise channels. Studios with consistently positive "
            "surprises demonstrate superior content development and marketing capabilities."
        )


class StudioMarketShare(BaseFactor):
    """Factor measuring studio's share of total box office market.

    This factor captures a studio's competitive position in the theatrical
    market. Higher market share indicates stronger content slate and
    competitive positioning.

    The factor is computed as:
        market_share = studio_gross / total_market_gross
    """

    factor_id = "studio_market_share"
    name = "Studio Market Share"
    description = "Measures studio's share of total box office revenue"
    domain = "entertainment"
    primary_entities = PRIMARY_TICKERS

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute studio market share factor.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (defaults to primary entities)

        Returns:
            List of FactorResult for each ticker
        """
        if tickers is None:
            tickers = self.primary_entities

        results = []

        async with get_async_session() as session:
            # Use trailing 30-day window for market share
            lookback_start = as_of_date - timedelta(days=30)

            # Get total market gross
            total_market = await self._get_total_market_gross(
                session, lookback_start, as_of_date
            )

            if total_market <= 0:
                # No market data - return neutral factors
                for ticker in tickers:
                    results.append(FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal("0"),
                        variance=Decimal("0.01"),
                        data_quality=Decimal("0.3"),
                        metadata={"no_market_data": True}
                    ))
                return results

            # Get studio gross and compute market share for each ticker
            for ticker in tickers:
                studio_gross = await self._get_studio_gross(
                    session, ticker, lookback_start, as_of_date
                )

                market_share = float(studio_gross / total_market) if total_market > 0 else 0.0

                # Compute rolling variance from daily shares
                daily_shares = await self._get_daily_shares(
                    session, ticker, lookback_start, as_of_date
                )
                variance = self._compute_variance(daily_shares, market_share) if daily_shares else 0.001

                results.append(FactorResult(
                    ticker=ticker,
                    factor_id=self.factor_id,
                    as_of_date=as_of_date,
                    mean=Decimal(str(round(market_share, 6))),
                    variance=Decimal(str(round(variance, 6))),
                    data_quality=self._compute_data_quality(studio_gross, total_market),
                    metadata={
                        "studio_gross": float(studio_gross),
                        "total_market": float(total_market),
                        "lookback_days": 30,
                    }
                ))

        return results

    async def _get_total_market_gross(
        self,
        session: AsyncSession,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        """Get total market gross for the period."""
        query = select(func.sum(BoxOfficeDaily.daily_gross)).where(
            BoxOfficeDaily.date >= start_date,
            BoxOfficeDaily.date <= end_date,
        )
        result = await session.execute(query)
        total = result.scalar_one_or_none()
        return total or Decimal("0")

    async def _get_studio_gross(
        self,
        session: AsyncSession,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        """Get studio gross for the period."""
        query = select(func.sum(BoxOfficeDaily.daily_gross)).where(
            BoxOfficeDaily.distributor_ticker == ticker,
            BoxOfficeDaily.date >= start_date,
            BoxOfficeDaily.date <= end_date,
        )
        result = await session.execute(query)
        total = result.scalar_one_or_none()
        return total or Decimal("0")

    async def _get_daily_shares(
        self,
        session: AsyncSession,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> list[float]:
        """Get daily market share values for variance computation."""
        # Get daily totals for studio
        studio_query = (
            select(
                BoxOfficeDaily.date,
                func.sum(BoxOfficeDaily.daily_gross).label("studio_gross")
            )
            .where(
                BoxOfficeDaily.distributor_ticker == ticker,
                BoxOfficeDaily.date >= start_date,
                BoxOfficeDaily.date <= end_date,
            )
            .group_by(BoxOfficeDaily.date)
        )

        # Get daily market totals
        market_query = (
            select(
                BoxOfficeDaily.date,
                func.sum(BoxOfficeDaily.daily_gross).label("market_gross")
            )
            .where(
                BoxOfficeDaily.date >= start_date,
                BoxOfficeDaily.date <= end_date,
            )
            .group_by(BoxOfficeDaily.date)
        )

        studio_result = await session.execute(studio_query)
        studio_by_date = {row.date: row.studio_gross for row in studio_result}

        market_result = await session.execute(market_query)
        market_by_date = {row.date: row.market_gross for row in market_result}

        daily_shares = []
        for dt, market_gross in market_by_date.items():
            if market_gross and market_gross > 0:
                studio_gross = studio_by_date.get(dt, Decimal("0"))
                share = float(studio_gross / market_gross)
                daily_shares.append(share)

        return daily_shares

    def _compute_variance(self, values: list[float], mean: float) -> float:
        """Compute variance of market share values."""
        if len(values) < 2:
            return 0.001
        return sum((v - mean) ** 2 for v in values) / (len(values) - 1)

    def _compute_data_quality(
        self,
        studio_gross: Decimal,
        total_market: Decimal,
    ) -> Decimal:
        """Compute data quality based on data availability."""
        if total_market <= 0:
            return Decimal("0.3")
        if studio_gross <= 0:
            return Decimal("0.5")

        # Higher quality for larger sample
        share = float(studio_gross / total_market)
        if share >= 0.05:  # At least 5% market share
            return Decimal("1.0")
        elif share >= 0.01:
            return Decimal("0.9")
        else:
            return Decimal("0.7")

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"MS_t = \frac{\sum_{i \in S} G_{i,t}}{\sum_{j \in M} G_{j,t}}"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return (
            "Market share is a key competitive indicator for entertainment studios. "
            "Higher market share indicates stronger content slate, better marketing, "
            "and superior theatrical distribution. Studios gaining market share "
            "demonstrate improving competitive position and may benefit from "
            "operating leverage as fixed costs are spread over larger revenue base. "
            "Market share trends also signal content pipeline strength."
        )


# Export all factors
BOXOFFICE_FACTORS = [
    OpeningWeekendSurprise,
    StudioMarketShare,
]

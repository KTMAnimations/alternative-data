"""Restaurant sector factors derived from OpenTable seated diners data."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_session
from src.models.data_sources import OpenTableMetrics
from src.transformations.factors.base import BaseFactor, FactorResult

logger = structlog.get_logger()


# Primary restaurant sector entities
PRIMARY_ENTITIES = ["DRI", "MCD", "SBUX", "CMG", "YUM"]

# Expected regions for spread calculations
EXPECTED_REGIONS = ["US", "UK", "Germany", "Australia", "Canada"]


class SeatedDinersMomentum(BaseFactor):
    """Week-over-Week change in Year-over-Year seated diners.

    This factor captures the momentum in restaurant traffic by measuring
    how the YoY comparison is changing week-to-week. Positive momentum
    suggests accelerating recovery or growth.

    Formula: WoW_change = YoY_t - YoY_{t-1}
    """

    factor_id: str = "seated_diners_momentum"
    name: str = "Seated Diners Momentum"
    description: str = "Week-over-week change in year-over-year seated diners percentage"
    domain: str = "restaurant"
    primary_entities: list[str] = PRIMARY_ENTITIES

    def __init__(self, region: str = "US"):
        """Initialize the factor.

        Args:
            region: Target region for the factor (default: US)
        """
        super().__init__()
        self.region = region

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute the seated diners momentum factor.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (defaults to primary entities)

        Returns:
            List of FactorResult objects for each ticker
        """
        target_tickers = tickers or self.primary_entities

        # Get the most recent week ending on or before as_of_date
        async with get_async_session() as session:
            wow_change = await self._get_wow_change(session, as_of_date)

        if wow_change is None:
            self.logger.warning(
                "No WoW change data available",
                as_of_date=as_of_date,
                region=self.region,
            )
            return []

        # Calculate variance using historical data
        variance = await self._calculate_variance(as_of_date)

        results = []
        for ticker in target_tickers:
            results.append(
                FactorResult(
                    ticker=ticker,
                    factor_id=self.factor_id,
                    as_of_date=as_of_date,
                    mean=wow_change,
                    variance=variance,
                    data_quality=Decimal("1.0"),
                    revision_status="original",
                    metadata={
                        "region": self.region,
                        "source": "opentable",
                    },
                )
            )

        return results

    async def _get_wow_change(
        self,
        session: AsyncSession,
        as_of_date: date,
    ) -> Optional[Decimal]:
        """Get WoW change for the most recent week.

        Args:
            session: Database session
            as_of_date: Date to look up

        Returns:
            WoW change percentage or None if not available
        """
        # Find the most recent week ending on or before as_of_date
        result = await session.execute(
            select(OpenTableMetrics.wow_change_pct)
            .where(
                OpenTableMetrics.region == self.region,
                OpenTableMetrics.city.is_(None),
                OpenTableMetrics.week_ending <= as_of_date,
            )
            .order_by(OpenTableMetrics.week_ending.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _calculate_variance(
        self,
        as_of_date: date,
        lookback_weeks: int = 52,
    ) -> Decimal:
        """Calculate variance of WoW changes over lookback period.

        Args:
            as_of_date: Reference date
            lookback_weeks: Number of weeks to look back (default: 52)

        Returns:
            Variance of WoW changes
        """
        start_date = as_of_date - timedelta(weeks=lookback_weeks)
        variance = None

        async with get_async_session() as session:
            result = await session.execute(
                select(func.var_pop(OpenTableMetrics.wow_change_pct))
                .where(
                    OpenTableMetrics.region == self.region,
                    OpenTableMetrics.city.is_(None),
                    OpenTableMetrics.week_ending >= start_date,
                    OpenTableMetrics.week_ending <= as_of_date,
                    OpenTableMetrics.wow_change_pct.isnot(None),
                )
            )
            variance = result.scalar_one_or_none()

        return Decimal(str(variance)) if variance else Decimal("0.01")

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"WoW\_Momentum_t = YoY_t - YoY_{t-1}"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        The Seated Diners Momentum factor captures the rate of change in restaurant
        traffic trends. When YoY comparisons are improving week-over-week, it signals
        accelerating consumer demand for dining out, which is a leading indicator for
        restaurant sector revenue. This factor is particularly useful for identifying
        inflection points in dining trends.

        Positive values indicate improving momentum (YoY getting better).
        Negative values indicate deteriorating momentum (YoY getting worse).
        """


class RegionalDiningSpread(BaseFactor):
    """Max-min spread in YoY seated diners across regions.

    This factor measures the dispersion in dining recovery/growth across
    geographic regions. High spread suggests uneven economic conditions,
    while low spread indicates synchronized dining trends globally.

    Formula: Spread = max(YoY_regions) - min(YoY_regions)
    """

    factor_id: str = "regional_dining_spread"
    name: str = "Regional Dining Spread"
    description: str = "Max-min spread in YoY seated diners across regions"
    domain: str = "restaurant"
    primary_entities: list[str] = PRIMARY_ENTITIES

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute the regional dining spread factor.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (defaults to primary entities)

        Returns:
            List of FactorResult objects for each ticker
        """
        target_tickers = tickers or self.primary_entities

        async with get_async_session() as session:
            spread_data = await self._get_regional_spread(session, as_of_date)

        if spread_data is None:
            self.logger.warning(
                "Could not calculate regional spread",
                as_of_date=as_of_date,
            )
            return []

        spread, max_region, min_region, variance = spread_data

        results = []
        for ticker in target_tickers:
            results.append(
                FactorResult(
                    ticker=ticker,
                    factor_id=self.factor_id,
                    as_of_date=as_of_date,
                    mean=spread,
                    variance=variance,
                    data_quality=Decimal("1.0"),
                    revision_status="original",
                    metadata={
                        "max_region": max_region,
                        "min_region": min_region,
                        "source": "opentable",
                    },
                )
            )

        return results

    async def _get_regional_spread(
        self,
        session: AsyncSession,
        as_of_date: date,
    ) -> Optional[tuple[Decimal, str, str, Decimal]]:
        """Calculate regional spread for the most recent week.

        Args:
            session: Database session
            as_of_date: Date to look up

        Returns:
            Tuple of (spread, max_region, min_region, variance) or None
        """
        # Get the most recent week with data for all regions
        week_result = await session.execute(
            select(OpenTableMetrics.week_ending)
            .where(
                OpenTableMetrics.city.is_(None),
                OpenTableMetrics.week_ending <= as_of_date,
            )
            .order_by(OpenTableMetrics.week_ending.desc())
            .limit(1)
        )
        week_ending = week_result.scalar_one_or_none()

        if week_ending is None:
            return None

        # Get all regional data for that week
        result = await session.execute(
            select(
                OpenTableMetrics.region,
                OpenTableMetrics.yoy_seated_diners_pct,
            )
            .where(
                OpenTableMetrics.week_ending == week_ending,
                OpenTableMetrics.city.is_(None),
                OpenTableMetrics.region.in_(EXPECTED_REGIONS),
            )
        )
        regional_data = {row.region: row.yoy_seated_diners_pct for row in result.fetchall()}

        if len(regional_data) < 2:
            return None

        max_yoy = max(regional_data.values())
        min_yoy = min(regional_data.values())
        spread = max_yoy - min_yoy

        max_region = [k for k, v in regional_data.items() if v == max_yoy][0]
        min_region = [k for k, v in regional_data.items() if v == min_yoy][0]

        # Calculate variance from historical spreads
        variance = await self._calculate_spread_variance(session, as_of_date)

        return (spread, max_region, min_region, variance)

    async def _calculate_spread_variance(
        self,
        session: AsyncSession,
        as_of_date: date,
        lookback_weeks: int = 52,
    ) -> Decimal:
        """Calculate historical variance of regional spreads.

        Args:
            session: Database session
            as_of_date: Reference date
            lookback_weeks: Number of weeks to look back

        Returns:
            Variance of spreads
        """
        start_date = as_of_date - timedelta(weeks=lookback_weeks)

        # Get historical spreads
        result = await session.execute(
            select(
                OpenTableMetrics.week_ending,
                func.max(OpenTableMetrics.yoy_seated_diners_pct).label("max_yoy"),
                func.min(OpenTableMetrics.yoy_seated_diners_pct).label("min_yoy"),
            )
            .where(
                OpenTableMetrics.city.is_(None),
                OpenTableMetrics.week_ending >= start_date,
                OpenTableMetrics.week_ending <= as_of_date,
                OpenTableMetrics.region.in_(EXPECTED_REGIONS),
            )
            .group_by(OpenTableMetrics.week_ending)
        )

        spreads = []
        for row in result.fetchall():
            if row.max_yoy is not None and row.min_yoy is not None:
                spreads.append(float(row.max_yoy - row.min_yoy))

        if len(spreads) < 2:
            return Decimal("1.0")

        mean = sum(spreads) / len(spreads)
        variance = sum((x - mean) ** 2 for x in spreads) / len(spreads)

        return Decimal(str(variance)) if variance > 0 else Decimal("1.0")

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"Spread_t = \max_r(YoY_{r,t}) - \min_r(YoY_{r,t})"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        The Regional Dining Spread factor measures the dispersion of dining
        trends across major markets. A high spread indicates divergent economic
        conditions across regions - some markets may be thriving while others
        struggle. This is important for multi-national restaurant chains as
        it signals geographic concentration risk.

        For global chains (MCD, SBUX, YUM), high spread may indicate opportunity
        to reallocate resources. For domestic-focused chains (DRI, CMG), US
        relative performance vs other regions signals competitive positioning.
        """


class RestaurantSectorHealth(BaseFactor):
    """4-week rolling average restaurant sector health score (0-100).

    This factor provides a normalized view of overall restaurant sector
    health by transforming the rolling average YoY seated diners into
    a 0-100 scale where 50 represents flat YoY and higher values
    indicate growth.

    Formula: Health = 50 + (rolling_avg_YoY / 2), clamped to [0, 100]
    """

    factor_id: str = "restaurant_sector_health"
    name: str = "Restaurant Sector Health"
    description: str = "4-week rolling average sector health score (0-100)"
    domain: str = "restaurant"
    primary_entities: list[str] = PRIMARY_ENTITIES

    def __init__(self, region: str = "US", rolling_weeks: int = 4):
        """Initialize the factor.

        Args:
            region: Target region for the factor (default: US)
            rolling_weeks: Number of weeks for rolling average (default: 4)
        """
        super().__init__()
        self.region = region
        self.rolling_weeks = rolling_weeks

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute the restaurant sector health factor.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (defaults to primary entities)

        Returns:
            List of FactorResult objects for each ticker
        """
        target_tickers = tickers or self.primary_entities

        async with get_async_session() as session:
            health_data = await self._calculate_health_score(session, as_of_date)

        if health_data is None:
            self.logger.warning(
                "Could not calculate health score",
                as_of_date=as_of_date,
                region=self.region,
            )
            return []

        health_score, rolling_avg, variance = health_data

        results = []
        for ticker in target_tickers:
            results.append(
                FactorResult(
                    ticker=ticker,
                    factor_id=self.factor_id,
                    as_of_date=as_of_date,
                    mean=health_score,
                    variance=variance,
                    data_quality=Decimal("1.0"),
                    revision_status="original",
                    metadata={
                        "region": self.region,
                        "rolling_weeks": self.rolling_weeks,
                        "rolling_avg_yoy": str(rolling_avg),
                        "source": "opentable",
                    },
                )
            )

        return results

    async def _calculate_health_score(
        self,
        session: AsyncSession,
        as_of_date: date,
    ) -> Optional[tuple[Decimal, Decimal, Decimal]]:
        """Calculate the health score based on rolling average.

        Args:
            session: Database session
            as_of_date: Date to compute for

        Returns:
            Tuple of (health_score, rolling_avg, variance) or None
        """
        start_date = as_of_date - timedelta(weeks=self.rolling_weeks)

        # Get YoY values for the rolling period
        result = await session.execute(
            select(
                func.avg(OpenTableMetrics.yoy_seated_diners_pct).label("avg_yoy"),
                func.count(OpenTableMetrics.id).label("count"),
            )
            .where(
                OpenTableMetrics.region == self.region,
                OpenTableMetrics.city.is_(None),
                OpenTableMetrics.week_ending > start_date,
                OpenTableMetrics.week_ending <= as_of_date,
            )
        )
        row = result.fetchone()

        if row is None or row.avg_yoy is None or row.count < 2:
            return None

        rolling_avg = Decimal(str(row.avg_yoy))

        # Transform to 0-100 scale
        # 50 = flat YoY (0%)
        # 100 = +100% YoY
        # 0 = -100% YoY
        health_score = Decimal("50") + (rolling_avg / Decimal("2"))

        # Clamp to [0, 100]
        health_score = max(Decimal("0"), min(Decimal("100"), health_score))

        # Calculate variance
        variance = await self._calculate_health_variance(session, as_of_date)

        return (health_score, rolling_avg, variance)

    async def _calculate_health_variance(
        self,
        session: AsyncSession,
        as_of_date: date,
        lookback_weeks: int = 52,
    ) -> Decimal:
        """Calculate historical variance of health scores.

        Args:
            session: Database session
            as_of_date: Reference date
            lookback_weeks: Number of weeks to look back

        Returns:
            Variance of health scores
        """
        # Get weekly YoY values for the lookback period
        start_date = as_of_date - timedelta(weeks=lookback_weeks + self.rolling_weeks)

        result = await session.execute(
            select(
                OpenTableMetrics.week_ending,
                OpenTableMetrics.yoy_seated_diners_pct,
            )
            .where(
                OpenTableMetrics.region == self.region,
                OpenTableMetrics.city.is_(None),
                OpenTableMetrics.week_ending >= start_date,
                OpenTableMetrics.week_ending <= as_of_date,
            )
            .order_by(OpenTableMetrics.week_ending)
        )

        yoy_values = [(row.week_ending, float(row.yoy_seated_diners_pct))
                      for row in result.fetchall()]

        if len(yoy_values) < self.rolling_weeks + 1:
            return Decimal("5.0")

        # Calculate rolling health scores
        health_scores = []
        for i in range(self.rolling_weeks, len(yoy_values)):
            window = [yoy_values[j][1] for j in range(i - self.rolling_weeks, i)]
            avg = sum(window) / len(window)
            health = 50 + (avg / 2)
            health = max(0, min(100, health))
            health_scores.append(health)

        if len(health_scores) < 2:
            return Decimal("5.0")

        mean = sum(health_scores) / len(health_scores)
        variance = sum((x - mean) ** 2 for x in health_scores) / len(health_scores)

        return Decimal(str(variance)) if variance > 0 else Decimal("5.0")

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"Health_t = \text{clamp}_{[0,100]}\left(50 + \frac{\bar{YoY}_{t-3:t}}{2}\right)"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        The Restaurant Sector Health factor provides a normalized, smoothed
        view of restaurant industry performance. The 4-week rolling average
        reduces noise from weekly volatility, while the 0-100 scale provides
        intuitive interpretation:

        - 75-100: Strong growth (YoY > +50%)
        - 50-75: Moderate growth (YoY 0-50%)
        - 25-50: Moderate decline (YoY -50% to 0%)
        - 0-25: Severe decline (YoY < -50%)

        This factor is useful for understanding the overall health of the
        casual dining and quick service restaurant sectors, which affects
        all primary entities in this space.
        """


# Factory function to get all restaurant factors
def get_restaurant_factors(region: str = "US") -> list[BaseFactor]:
    """Get all restaurant sector factors.

    Args:
        region: Target region for regional factors

    Returns:
        List of factor instances
    """
    return [
        SeatedDinersMomentum(region=region),
        RegionalDiningSpread(),
        RestaurantSectorHealth(region=region),
    ]

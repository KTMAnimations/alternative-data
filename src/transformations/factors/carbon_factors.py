"""Carbon intensity factors for UK energy market analysis.

Factors:
- CarbonIntensityTrend: Month-over-month carbon intensity change
- RenewableShareGrowth: Percentage point change in renewable generation share

Primary entities: NG.L (National Grid), SSE.L (SSE plc)
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
import structlog

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.transformations.factors.base import BaseFactor, FactorResult
from src.models.data_sources import CarbonIntensityReading
from src.core.database import get_async_session

logger = structlog.get_logger()

# Primary entities for UK carbon intensity factors
UK_ENERGY_ENTITIES = ["NG.L", "SSE.L"]


class CarbonIntensityTrend(BaseFactor):
    """Month-over-month carbon intensity change factor.

    Measures the percentage change in average carbon intensity from the
    previous month, indicating grid decarbonization trends.

    Economic rationale:
    - Declining carbon intensity indicates successful renewable integration
    - Affects carbon credit pricing and energy company valuations
    - Correlates with regulatory compliance and ESG ratings
    - Lower intensity often correlates with lower wholesale electricity costs
    """

    factor_id = "carbon_intensity_mom"
    name = "Carbon Intensity MoM Change"
    description = "Month-over-month percentage change in UK grid carbon intensity"
    domain = "energy"
    primary_entities = UK_ENERGY_ENTITIES

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
        region: str = "national",
    ) -> list[FactorResult]:
        """Compute month-over-month carbon intensity change.

        Args:
            as_of_date: Date to compute factor for
            tickers: Tickers to compute for (defaults to primary_entities)
            region: UK region code (defaults to national)

        Returns:
            List of FactorResult objects for each ticker
        """
        target_tickers = tickers or self.primary_entities

        # Calculate date ranges for current and prior month
        # Current month: from start of month to as_of_date
        current_month_start = as_of_date.replace(day=1)

        # Prior month: full previous month
        prior_month_end = current_month_start - timedelta(days=1)
        prior_month_start = prior_month_end.replace(day=1)

        async with get_async_session() as session:
            # Get current month average intensity
            current_avg = await self._get_average_intensity(
                session,
                region,
                datetime.combine(current_month_start, datetime.min.time()),
                datetime.combine(as_of_date, datetime.max.time())
            )

            # Get prior month average intensity
            prior_avg = await self._get_average_intensity(
                session,
                region,
                datetime.combine(prior_month_start, datetime.min.time()),
                datetime.combine(prior_month_end, datetime.max.time())
            )

            # Get variance of current month
            current_variance = await self._get_intensity_variance(
                session,
                region,
                datetime.combine(current_month_start, datetime.min.time()),
                datetime.combine(as_of_date, datetime.max.time())
            )

        if current_avg is None or prior_avg is None or prior_avg == 0:
            self.logger.warning(
                "Insufficient data for carbon intensity trend",
                as_of_date=as_of_date,
                current_avg=current_avg,
                prior_avg=prior_avg
            )
            return []

        # Calculate MoM change
        mom_change = ((current_avg - prior_avg) / prior_avg) * 100

        # Calculate data quality based on data coverage
        data_quality = await self._calculate_data_quality(
            session if 'session' in dir() else None,
            region,
            current_month_start,
            as_of_date
        )

        results = []
        for ticker in target_tickers:
            results.append(FactorResult(
                ticker=ticker,
                factor_id=self.factor_id,
                as_of_date=as_of_date,
                mean=Decimal(str(round(mom_change, 4))),
                variance=Decimal(str(round(current_variance or 0, 4))),
                data_quality=data_quality,
                revision_status="original",
                metadata={
                    "region": region,
                    "current_month_avg": round(current_avg, 2),
                    "prior_month_avg": round(prior_avg, 2),
                    "current_month_start": current_month_start.isoformat(),
                    "prior_month_start": prior_month_start.isoformat(),
                }
            ))

        return results

    async def _get_average_intensity(
        self,
        session: AsyncSession,
        region: str,
        start: datetime,
        end: datetime
    ) -> Optional[float]:
        """Get average carbon intensity for a time period."""
        result = await session.execute(
            select(func.avg(CarbonIntensityReading.intensity_actual))
            .where(
                CarbonIntensityReading.region == region,
                CarbonIntensityReading.timestamp >= start,
                CarbonIntensityReading.timestamp <= end,
                CarbonIntensityReading.intensity_actual.isnot(None)
            )
        )
        avg = result.scalar()

        # Fall back to forecast if no actual data
        if avg is None:
            result = await session.execute(
                select(func.avg(CarbonIntensityReading.intensity_forecast))
                .where(
                    CarbonIntensityReading.region == region,
                    CarbonIntensityReading.timestamp >= start,
                    CarbonIntensityReading.timestamp <= end
                )
            )
            avg = result.scalar()

        return float(avg) if avg is not None else None

    async def _get_intensity_variance(
        self,
        session: AsyncSession,
        region: str,
        start: datetime,
        end: datetime
    ) -> Optional[float]:
        """Get variance of carbon intensity for a time period."""
        # Use actual values, fall back to forecast
        result = await session.execute(
            select(func.variance(CarbonIntensityReading.intensity_actual))
            .where(
                CarbonIntensityReading.region == region,
                CarbonIntensityReading.timestamp >= start,
                CarbonIntensityReading.timestamp <= end,
                CarbonIntensityReading.intensity_actual.isnot(None)
            )
        )
        var = result.scalar()

        if var is None:
            result = await session.execute(
                select(func.variance(CarbonIntensityReading.intensity_forecast))
                .where(
                    CarbonIntensityReading.region == region,
                    CarbonIntensityReading.timestamp >= start,
                    CarbonIntensityReading.timestamp <= end
                )
            )
            var = result.scalar()

        return float(var) if var is not None else None

    async def _calculate_data_quality(
        self,
        session: Optional[AsyncSession],
        region: str,
        start: date,
        end: date
    ) -> Decimal:
        """Calculate data quality score based on coverage."""
        if session is None:
            return Decimal("0.5")

        # Expected readings: 48 per day (every 30 mins)
        days = (end - start).days + 1
        expected_readings = days * 48

        async with get_async_session() as session:
            result = await session.execute(
                select(func.count(CarbonIntensityReading.id))
                .where(
                    CarbonIntensityReading.region == region,
                    CarbonIntensityReading.timestamp >= datetime.combine(start, datetime.min.time()),
                    CarbonIntensityReading.timestamp <= datetime.combine(end, datetime.max.time())
                )
            )
            actual_readings = result.scalar() or 0

        coverage = min(actual_readings / expected_readings, 1.0) if expected_readings > 0 else 0
        return Decimal(str(round(coverage, 4)))

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"\text{CI}_{MoM} = \frac{\bar{I}_{t} - \bar{I}_{t-1}}{\bar{I}_{t-1}} \times 100"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        Carbon Intensity MoM Change measures the month-over-month percentage change
        in UK grid carbon intensity (gCO2/kWh).

        Economic significance for UK energy companies:
        1. Grid Decarbonization Progress: Declining intensity indicates successful
           integration of renewable sources, affecting National Grid's infrastructure
           investments and SSE's generation portfolio value.

        2. Carbon Pricing Impact: Lower grid intensity reduces carbon credit
           requirements and compliance costs for energy generators.

        3. Wholesale Price Correlation: Periods of low carbon intensity often
           coincide with high renewable output and lower wholesale prices.

        4. ESG Performance: Grid decarbonization directly impacts energy company
           ESG ratings and access to green financing.

        5. Regulatory Outlook: Consistent intensity reductions signal successful
           policy implementation, reducing regulatory risk.

        Negative values indicate decarbonization progress (typically positive
        for renewable-heavy generators like SSE, mixed for National Grid which
        earns transmission fees regardless of generation source).
        """


class RenewableShareGrowth(BaseFactor):
    """Renewable generation share growth factor.

    Measures the percentage point change in renewable generation share
    compared to the previous month.

    Economic rationale:
    - Higher renewable share indicates grid transformation progress
    - Affects capacity payments and ancillary services demand
    - Correlates with intermittency management costs
    - Impacts fossil fuel generator utilization rates
    """

    factor_id = "renewable_share_growth"
    name = "Renewable Share Growth"
    description = "Month-over-month change in renewable generation share (percentage points)"
    domain = "energy"
    primary_entities = UK_ENERGY_ENTITIES

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
        region: str = "national",
    ) -> list[FactorResult]:
        """Compute month-over-month renewable share change.

        Args:
            as_of_date: Date to compute factor for
            tickers: Tickers to compute for (defaults to primary_entities)
            region: UK region code (defaults to national)

        Returns:
            List of FactorResult objects for each ticker
        """
        target_tickers = tickers or self.primary_entities

        # Calculate date ranges
        current_month_start = as_of_date.replace(day=1)
        prior_month_end = current_month_start - timedelta(days=1)
        prior_month_start = prior_month_end.replace(day=1)

        async with get_async_session() as session:
            # Get current month average renewable percentage
            current_avg = await self._get_average_renewable_pct(
                session,
                region,
                datetime.combine(current_month_start, datetime.min.time()),
                datetime.combine(as_of_date, datetime.max.time())
            )

            # Get prior month average renewable percentage
            prior_avg = await self._get_average_renewable_pct(
                session,
                region,
                datetime.combine(prior_month_start, datetime.min.time()),
                datetime.combine(prior_month_end, datetime.max.time())
            )

            # Get variance
            current_variance = await self._get_renewable_variance(
                session,
                region,
                datetime.combine(current_month_start, datetime.min.time()),
                datetime.combine(as_of_date, datetime.max.time())
            )

        if current_avg is None or prior_avg is None:
            self.logger.warning(
                "Insufficient data for renewable share growth",
                as_of_date=as_of_date,
                current_avg=current_avg,
                prior_avg=prior_avg
            )
            return []

        # Calculate percentage point change (not percentage change)
        pp_change = current_avg - prior_avg

        # Calculate data quality
        data_quality = await self._calculate_data_quality(
            region,
            current_month_start,
            as_of_date
        )

        results = []
        for ticker in target_tickers:
            results.append(FactorResult(
                ticker=ticker,
                factor_id=self.factor_id,
                as_of_date=as_of_date,
                mean=Decimal(str(round(pp_change, 4))),
                variance=Decimal(str(round(current_variance or 0, 4))),
                data_quality=data_quality,
                revision_status="original",
                metadata={
                    "region": region,
                    "current_month_avg_pct": round(current_avg, 2),
                    "prior_month_avg_pct": round(prior_avg, 2),
                    "current_month_start": current_month_start.isoformat(),
                    "prior_month_start": prior_month_start.isoformat(),
                }
            ))

        return results

    async def _get_average_renewable_pct(
        self,
        session: AsyncSession,
        region: str,
        start: datetime,
        end: datetime
    ) -> Optional[float]:
        """Get average renewable percentage for a time period."""
        result = await session.execute(
            select(func.avg(CarbonIntensityReading.renewable_pct))
            .where(
                CarbonIntensityReading.region == region,
                CarbonIntensityReading.timestamp >= start,
                CarbonIntensityReading.timestamp <= end
            )
        )
        avg = result.scalar()
        return float(avg) if avg is not None else None

    async def _get_renewable_variance(
        self,
        session: AsyncSession,
        region: str,
        start: datetime,
        end: datetime
    ) -> Optional[float]:
        """Get variance of renewable percentage for a time period."""
        result = await session.execute(
            select(func.variance(CarbonIntensityReading.renewable_pct))
            .where(
                CarbonIntensityReading.region == region,
                CarbonIntensityReading.timestamp >= start,
                CarbonIntensityReading.timestamp <= end
            )
        )
        var = result.scalar()
        return float(var) if var is not None else None

    async def _calculate_data_quality(
        self,
        region: str,
        start: date,
        end: date
    ) -> Decimal:
        """Calculate data quality score based on coverage."""
        days = (end - start).days + 1
        expected_readings = days * 48  # 48 half-hour periods per day

        async with get_async_session() as session:
            result = await session.execute(
                select(func.count(CarbonIntensityReading.id))
                .where(
                    CarbonIntensityReading.region == region,
                    CarbonIntensityReading.timestamp >= datetime.combine(start, datetime.min.time()),
                    CarbonIntensityReading.timestamp <= datetime.combine(end, datetime.max.time())
                )
            )
            actual_readings = result.scalar() or 0

        coverage = min(actual_readings / expected_readings, 1.0) if expected_readings > 0 else 0
        return Decimal(str(round(coverage, 4)))

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"\text{RSG} = \bar{R}_{t} - \bar{R}_{t-1}"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        Renewable Share Growth measures the month-over-month change in the
        percentage of UK electricity generated from renewable sources
        (solar, wind, hydro, biomass).

        Economic significance for UK energy companies:
        1. Generation Portfolio Value: For SSE with significant renewable capacity,
           higher renewable share indicates stronger market position and revenue
           potential from their wind and hydro assets.

        2. Capacity Market Impact: Higher renewable penetration increases demand
           for balancing services and capacity payments, affecting National Grid's
           system operator revenues.

        3. Intermittency Costs: Rapid renewable share growth correlates with
           increased grid management complexity and costs.

        4. Fossil Fuel Displacement: Higher renewable share reduces dispatch
           hours for gas-fired plants, affecting CCGTs owned by energy majors.

        5. Investment Signals: Consistent renewable share growth validates
           renewable energy investments and project pipelines.

        Positive values indicate growth in renewable generation, typically
        favorable for renewable-focused generators and potentially increasing
        grid management requirements for National Grid.
        """


# Factory functions for creating factors
def create_carbon_intensity_trend() -> CarbonIntensityTrend:
    """Create a CarbonIntensityTrend factor instance."""
    return CarbonIntensityTrend()


def create_renewable_share_growth() -> RenewableShareGrowth:
    """Create a RenewableShareGrowth factor instance."""
    return RenewableShareGrowth()


# Registry of all carbon-related factors
CARBON_FACTORS = {
    "carbon_intensity_mom": CarbonIntensityTrend,
    "renewable_share_growth": RenewableShareGrowth,
}

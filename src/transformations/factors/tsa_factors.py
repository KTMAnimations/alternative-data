"""TSA-based factors for airline and travel industry analysis.

Factors derived from TSA checkpoint throughput data:
- TSAThroughputMomentum: 7-day rolling average vs prior year
- TSAWeekdayWeekendRatio: Business vs leisure travel mix
- TSAAirlineEnplanementNowcast: Monthly enplanement estimate

Primary entities: DAL, UAL, AAL, LUV, JBLU, JETS
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_session
from src.models.data_sources import TSACheckpoint
from src.transformations.factors.base import BaseFactor, FactorResult


# Primary entities for TSA-based factors
TSA_PRIMARY_ENTITIES = ["DAL", "UAL", "AAL", "LUV", "JBLU", "JETS"]

# Market share estimates for weighting (based on domestic capacity)
AIRLINE_MARKET_SHARES = {
    "DAL": Decimal("0.18"),   # Delta
    "UAL": Decimal("0.16"),   # United
    "AAL": Decimal("0.20"),   # American
    "LUV": Decimal("0.17"),   # Southwest
    "JBLU": Decimal("0.06"),  # JetBlue
    "JETS": Decimal("1.00"),  # ETF tracks entire sector
}


class TSAThroughputMomentum(BaseFactor):
    """7-day rolling average throughput vs prior year same period.

    This factor captures short-term momentum in passenger demand
    relative to the same period last year, smoothing out daily noise.

    Positive values indicate accelerating passenger growth.
    Negative values indicate decelerating demand.

    Economic Rationale:
    - Leading indicator for airline revenue trends
    - Captures demand shifts before earnings reports
    - Useful for detecting holiday travel patterns
    """

    factor_id = "tsa_throughput_momentum"
    name = "TSA Throughput Momentum"
    description = "7-day rolling average passenger throughput YoY change"
    domain = "travel"
    primary_entities = TSA_PRIMARY_ENTITIES

    LOOKBACK_DAYS = 7

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute 7-day rolling throughput momentum.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (defaults to primary_entities)

        Returns:
            List of FactorResult objects for each ticker
        """
        tickers = tickers or self.primary_entities

        # Get 7-day window data
        start_date = as_of_date - timedelta(days=self.LOOKBACK_DAYS - 1)

        async with get_async_session() as session:
            result = await session.execute(
                select(
                    TSACheckpoint.date,
                    TSACheckpoint.current_year_throughput,
                    TSACheckpoint.prior_year_throughput,
                    TSACheckpoint.yoy_change_pct,
                    TSACheckpoint.data_quality_score,
                )
                .where(TSACheckpoint.date >= start_date)
                .where(TSACheckpoint.date <= as_of_date)
                .order_by(TSACheckpoint.date)
            )
            rows = result.fetchall()

        if len(rows) < self.LOOKBACK_DAYS:
            self.logger.warning(
                "Insufficient data for momentum calculation",
                required=self.LOOKBACK_DAYS,
                available=len(rows),
            )
            return []

        # Calculate rolling averages
        current_avg = Decimal(sum(r[1] for r in rows)) / len(rows)
        prior_avg = Decimal(sum(r[2] for r in rows if r[2])) / len([r for r in rows if r[2]])

        # Calculate momentum (YoY change in rolling avg)
        momentum = ((current_avg - prior_avg) / prior_avg * 100).quantize(Decimal("0.0001"))

        # Calculate variance from daily YoY changes
        yoy_changes = [r[3] for r in rows if r[3] is not None]
        if yoy_changes:
            mean_yoy = sum(yoy_changes) / len(yoy_changes)
            variance = sum((x - mean_yoy) ** 2 for x in yoy_changes) / len(yoy_changes)
        else:
            variance = Decimal("0")

        # Calculate weighted data quality
        avg_quality = sum(r[4] for r in rows) / len(rows)

        # Generate results for each ticker
        results = []
        for ticker in tickers:
            if ticker not in AIRLINE_MARKET_SHARES:
                continue

            # Apply market share weighting for individual airlines
            market_share = AIRLINE_MARKET_SHARES[ticker]
            ticker_momentum = momentum if ticker == "JETS" else momentum * market_share

            results.append(FactorResult(
                ticker=ticker,
                factor_id=self.factor_id,
                as_of_date=as_of_date,
                mean=ticker_momentum,
                variance=Decimal(str(variance)).quantize(Decimal("0.0001")),
                data_quality=avg_quality,
                revision_status="original",
                metadata={
                    "lookback_days": self.LOOKBACK_DAYS,
                    "current_avg_throughput": int(current_avg),
                    "prior_avg_throughput": int(prior_avg),
                    "data_points": len(rows),
                }
            ))

        return results

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"""
        \text{Momentum}_t = \frac{\bar{T}^{curr}_{t-6:t} - \bar{T}^{prior}_{t-6:t}}{\bar{T}^{prior}_{t-6:t}} \times 100

        \text{where } \bar{T} = \frac{1}{7}\sum_{i=0}^{6} T_{t-i}
        """

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        TSA throughput momentum captures short-term trends in passenger demand
        relative to the prior year. This is a leading indicator for airline
        revenues as it reflects actual passenger volumes rather than booked
        tickets or load factors.

        Key characteristics:
        - 7-day rolling average smooths daily volatility
        - YoY comparison controls for seasonal patterns
        - Captures holiday travel shifts and demand shocks

        Signal interpretation:
        - Positive momentum: Accelerating demand, positive for airline stocks
        - Negative momentum: Decelerating demand, cautionary signal
        - Values > 10%: Strong recovery or surge periods
        - Values < -10%: Significant demand weakness
        """


class TSAWeekdayWeekendRatio(BaseFactor):
    """Ratio of weekday to weekend throughput.

    This factor captures the mix between business travel (weekday heavy)
    and leisure travel (weekend heavy).

    Higher values indicate more business travel relative to leisure.
    Lower values indicate leisure-dominated travel patterns.

    Economic Rationale:
    - Business travel typically has higher margins for airlines
    - Shifts in mix can predict revenue quality changes
    - Useful for corporate travel trend analysis
    """

    factor_id = "tsa_weekday_weekend_ratio"
    name = "TSA Weekday/Weekend Ratio"
    description = "Ratio of weekday to weekend passenger throughput"
    domain = "travel"
    primary_entities = TSA_PRIMARY_ENTITIES

    LOOKBACK_WEEKS = 4  # Use 4 weeks for stable ratio

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute weekday/weekend throughput ratio.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (defaults to primary_entities)

        Returns:
            List of FactorResult objects for each ticker
        """
        tickers = tickers or self.primary_entities

        # Get 4-week window
        start_date = as_of_date - timedelta(weeks=self.LOOKBACK_WEEKS)

        async with get_async_session() as session:
            result = await session.execute(
                select(
                    TSACheckpoint.day_of_week,
                    TSACheckpoint.current_year_throughput,
                    TSACheckpoint.data_quality_score,
                )
                .where(TSACheckpoint.date >= start_date)
                .where(TSACheckpoint.date <= as_of_date)
            )
            rows = result.fetchall()

        if len(rows) < 7:
            self.logger.warning(
                "Insufficient data for ratio calculation",
                available=len(rows),
            )
            return []

        # Separate weekday and weekend throughput
        weekday_throughput = [r[1] for r in rows if r[0] < 5]  # Mon-Fri
        weekend_throughput = [r[1] for r in rows if r[0] >= 5]  # Sat-Sun

        if not weekend_throughput:
            self.logger.warning("No weekend data available")
            return []

        # Calculate averages
        avg_weekday = Decimal(sum(weekday_throughput)) / len(weekday_throughput) if weekday_throughput else Decimal("0")
        avg_weekend = Decimal(sum(weekend_throughput)) / len(weekend_throughput)

        # Calculate ratio
        ratio = (avg_weekday / avg_weekend).quantize(Decimal("0.0001"))

        # Calculate variance
        all_ratios = []
        for week_offset in range(self.LOOKBACK_WEEKS):
            week_start = start_date + timedelta(weeks=week_offset)
            week_end = week_start + timedelta(days=6)
            week_data = [r for r in rows if week_start <= as_of_date - timedelta(days=(as_of_date - week_start).days % 7)]
            if week_data:
                wd = [r[1] for r in week_data if r[0] < 5]
                we = [r[1] for r in week_data if r[0] >= 5]
                if wd and we:
                    all_ratios.append(Decimal(sum(wd)) / len(wd) / (Decimal(sum(we)) / len(we)))

        if all_ratios:
            mean_ratio = sum(all_ratios) / len(all_ratios)
            variance = sum((x - mean_ratio) ** 2 for x in all_ratios) / len(all_ratios)
        else:
            variance = Decimal("0")

        # Calculate data quality
        avg_quality = sum(r[2] for r in rows) / len(rows)

        # Generate results for each ticker
        results = []
        for ticker in tickers:
            if ticker not in AIRLINE_MARKET_SHARES:
                continue

            results.append(FactorResult(
                ticker=ticker,
                factor_id=self.factor_id,
                as_of_date=as_of_date,
                mean=ratio,
                variance=Decimal(str(variance)).quantize(Decimal("0.0001")),
                data_quality=avg_quality,
                revision_status="original",
                metadata={
                    "lookback_weeks": self.LOOKBACK_WEEKS,
                    "avg_weekday_throughput": int(avg_weekday),
                    "avg_weekend_throughput": int(avg_weekend),
                    "weekday_count": len(weekday_throughput),
                    "weekend_count": len(weekend_throughput),
                }
            ))

        return results

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"""
        \text{Ratio}_t = \frac{\bar{T}^{weekday}_{4w}}{\bar{T}^{weekend}_{4w}}

        \text{where } \bar{T}^{weekday} = \text{avg throughput Mon-Fri}

        \text{and } \bar{T}^{weekend} = \text{avg throughput Sat-Sun}
        """

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        The weekday/weekend ratio captures the mix between business and
        leisure travel. Business travelers typically fly on weekdays and
        generate higher revenue per passenger due to last-minute bookings
        and premium cabin purchases.

        Key characteristics:
        - Higher ratio (>1.2): Business travel dominance
        - Lower ratio (<1.0): Leisure travel dominance
        - Normal range: 1.05-1.15

        Signal interpretation:
        - Rising ratio: Business travel recovery, positive for yields
        - Falling ratio: Leisure shift, potential margin pressure
        - Ratio < 1: Unusual pattern (holidays, disruptions)

        Sector implications:
        - High business mix benefits Delta (DAL), United (UAL)
        - High leisure mix benefits Southwest (LUV), JetBlue (JBLU)
        """


class TSAAirlineEnplanementNowcast(BaseFactor):
    """Nowcast monthly airline enplanements from daily TSA data.

    Uses daily checkpoint data to estimate month-to-date enplanements
    and project full-month totals before official DOT data is released.

    Economic Rationale:
    - DOT enplanement data lags by 2-3 months
    - TSA data is available daily with 1-day lag
    - Provides early signal for airline load factors and revenue
    """

    factor_id = "tsa_enplanement_nowcast"
    name = "TSA Airline Enplanement Nowcast"
    description = "Monthly enplanement estimate from daily TSA throughput"
    domain = "travel"
    primary_entities = TSA_PRIMARY_ENTITIES

    # TSA throughput to enplanement conversion factor
    # (TSA counts departing passengers, enplanements count boardings)
    # Typical ratio is ~0.98 (some connecting passengers counted once)
    TSA_TO_ENPLANEMENT_FACTOR = Decimal("0.98")

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute monthly enplanement nowcast.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (defaults to primary_entities)

        Returns:
            List of FactorResult objects for each ticker
        """
        tickers = tickers or self.primary_entities

        # Get current month data
        month_start = as_of_date.replace(day=1)

        async with get_async_session() as session:
            # Get current month throughput
            current_result = await session.execute(
                select(
                    func.sum(TSACheckpoint.current_year_throughput),
                    func.avg(TSACheckpoint.current_year_throughput),
                    func.count(TSACheckpoint.id),
                    func.avg(TSACheckpoint.data_quality_score),
                )
                .where(TSACheckpoint.date >= month_start)
                .where(TSACheckpoint.date <= as_of_date)
            )
            current_row = current_result.fetchone()

            # Get prior year same month for comparison
            prior_month_start = month_start.replace(year=month_start.year - 1)
            prior_month_end = as_of_date.replace(year=as_of_date.year - 1)

            prior_result = await session.execute(
                select(
                    func.sum(TSACheckpoint.prior_year_throughput),
                    func.count(TSACheckpoint.id),
                )
                .where(TSACheckpoint.date >= prior_month_start)
                .where(TSACheckpoint.date <= prior_month_end)
            )
            prior_row = prior_result.fetchone()

        if not current_row[0] or current_row[2] == 0:
            self.logger.warning("No data for current month")
            return []

        mtd_throughput = Decimal(str(current_row[0]))
        avg_daily = Decimal(str(current_row[1]))
        days_so_far = current_row[2]
        data_quality = Decimal(str(current_row[3])) if current_row[3] else Decimal("1.0")

        # Calculate days in month
        if as_of_date.month == 12:
            next_month = as_of_date.replace(year=as_of_date.year + 1, month=1, day=1)
        else:
            next_month = as_of_date.replace(month=as_of_date.month + 1, day=1)
        days_in_month = (next_month - month_start).days

        # Project full month enplanements
        projected_throughput = avg_daily * days_in_month
        projected_enplanements = (projected_throughput * self.TSA_TO_ENPLANEMENT_FACTOR / 1_000_000).quantize(Decimal("0.01"))

        # Calculate YoY change if prior data available
        prior_mtd = Decimal(str(prior_row[0])) if prior_row[0] else None
        yoy_change = None
        if prior_mtd and prior_mtd > 0:
            yoy_change = ((mtd_throughput - prior_mtd) / prior_mtd * 100).quantize(Decimal("0.01"))

        # Calculate variance based on projection uncertainty
        # More days = lower variance
        completion_pct = Decimal(days_so_far) / Decimal(days_in_month)
        base_variance = Decimal("0.01")  # 1% base variance
        variance = (base_variance / (completion_pct + Decimal("0.1"))).quantize(Decimal("0.0001"))

        # Generate results for each ticker
        results = []
        for ticker in tickers:
            if ticker not in AIRLINE_MARKET_SHARES:
                continue

            market_share = AIRLINE_MARKET_SHARES[ticker]

            # Estimate ticker-specific enplanements
            ticker_enplanements = (projected_enplanements * market_share).quantize(Decimal("0.01"))

            results.append(FactorResult(
                ticker=ticker,
                factor_id=self.factor_id,
                as_of_date=as_of_date,
                mean=ticker_enplanements,  # In millions
                variance=variance,
                data_quality=data_quality * completion_pct,  # Adjust quality for projection
                revision_status="preliminary" if days_so_far < days_in_month else "final",
                metadata={
                    "month": as_of_date.strftime("%Y-%m"),
                    "days_reported": days_so_far,
                    "days_in_month": days_in_month,
                    "completion_pct": float(completion_pct * 100),
                    "mtd_throughput_millions": float(mtd_throughput / 1_000_000),
                    "projected_throughput_millions": float(projected_throughput / 1_000_000),
                    "yoy_change_pct": float(yoy_change) if yoy_change else None,
                    "market_share": float(market_share),
                }
            ))

        return results

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"""
        \text{Enplanement}_t = \frac{T_{MTD}}{d_{so\_far}} \times d_{month} \times 0.98

        \text{where } T_{MTD} = \sum_{i=1}^{d_{so\_far}} T_i

        \text{and } d_{month} = \text{days in month}
        """

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        The enplanement nowcast provides an early estimate of monthly
        airline passenger volumes, typically 2-3 months before official
        DOT data is released.

        Key characteristics:
        - Uses daily TSA throughput as high-frequency proxy
        - Projects full-month total from month-to-date average
        - Applies 0.98 conversion factor (connecting passengers)
        - Weights by market share for ticker-specific estimates

        Signal interpretation:
        - Values in millions of enplanements
        - Compare to consensus estimates and prior year
        - Higher completion % = more reliable projection

        Data quality considerations:
        - Early month: High uncertainty (variance)
        - Late month: Near-final accuracy
        - Holiday months may have non-linear patterns
        """


# Factory function to get all TSA factors
def get_tsa_factors() -> list[BaseFactor]:
    """Return list of all TSA-based factors."""
    return [
        TSAThroughputMomentum(),
        TSAWeekdayWeekendRatio(),
        TSAAirlineEnplanementNowcast(),
    ]

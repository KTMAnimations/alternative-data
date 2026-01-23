"""Rental market factors based on Zillow ZORI data.

Factors:
- RentInflationIndex: ZORI YoY change as CPI leading indicator
- SFRMultifamilySpread: Single-family vs multi-family rent differential

Primary entities: EQR, AVB, MAA, INVH, AMH (REITs)
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select, and_

from src.transformations.factors.base import BaseFactor, FactorResult
from src.core.database import get_async_session
from src.models.data_sources import ZillowRentalIndex


class RentInflationIndex(BaseFactor):
    """ZORI Year-over-Year change as a CPI leading indicator.

    This factor captures rental inflation trends from Zillow's Observed
    Rent Index, which tends to lead official CPI shelter components by
    approximately 12 months.

    Economic Rationale:
    - Shelter costs represent ~33% of CPI
    - Market rents (ZORI) lead CPI shelter by 12+ months
    - Rent acceleration signals future CPI pressure
    - REITs benefit from pricing power during rent inflation

    Formula:
    RentInflationIndex = ZORI_YoY_Change / 100

    Where ZORI_YoY_Change is the year-over-year percentage change in
    the Zillow Observed Rent Index.
    """

    factor_id = "rent_inflation_index"
    name = "Rent Inflation Index"
    description = "ZORI year-over-year change as CPI leading indicator"
    domain = "real_estate"
    primary_entities = ["EQR", "AVB", "MAA", "INVH", "AMH"]

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute rent inflation index for given date and tickers.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers to compute for.
                    If None, compute for all primary entities.

        Returns:
            List of FactorResult objects
        """
        target_tickers = tickers or self.primary_entities
        results: list[FactorResult] = []

        async with get_async_session() as session:
            # Get ZORI data for the as_of_date period (first of month)
            target_period = date(as_of_date.year, as_of_date.month, 1)

            # Query national-level ZORI with YoY change
            stmt = select(ZillowRentalIndex).where(
                and_(
                    ZillowRentalIndex.period == target_period,
                    ZillowRentalIndex.geography_level == "national",
                    ZillowRentalIndex.property_type == "all",
                )
            )
            result = await session.execute(stmt)
            national_record = result.scalar_one_or_none()

            if not national_record:
                # Try to find the most recent period if exact match not found
                stmt = (
                    select(ZillowRentalIndex)
                    .where(
                        and_(
                            ZillowRentalIndex.period <= target_period,
                            ZillowRentalIndex.geography_level == "national",
                            ZillowRentalIndex.property_type == "all",
                        )
                    )
                    .order_by(ZillowRentalIndex.period.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                national_record = result.scalar_one_or_none()

            if not national_record or national_record.yoy_change_pct is None:
                self.logger.warning(
                    "No ZORI data available",
                    as_of_date=as_of_date,
                )
                return results

            # Convert YoY percentage to decimal factor
            yoy_change = national_record.yoy_change_pct / Decimal("100")

            # Calculate variance from historical YoY changes
            variance = await self._calculate_variance(session, target_period)

            # Apply factor to all target tickers
            for ticker in target_tickers:
                results.append(
                    FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=yoy_change,
                        variance=variance,
                        data_quality=self._calculate_data_quality(national_record),
                        revision_status="original",
                        metadata={
                            "zori_value": float(national_record.zori_value),
                            "yoy_change_pct": float(national_record.yoy_change_pct),
                            "period": national_record.period.isoformat(),
                            "geography_level": national_record.geography_level,
                        },
                    )
                )

        return results

    async def _calculate_variance(
        self,
        session,
        target_period: date,
        lookback_months: int = 12,
    ) -> Decimal:
        """Calculate variance from historical YoY changes."""
        start_period = date(
            target_period.year - 1 if target_period.month == 1 else target_period.year,
            12 if target_period.month == 1 else target_period.month - 1,
            1,
        )

        stmt = select(ZillowRentalIndex.yoy_change_pct).where(
            and_(
                ZillowRentalIndex.period >= start_period,
                ZillowRentalIndex.period <= target_period,
                ZillowRentalIndex.geography_level == "national",
                ZillowRentalIndex.property_type == "all",
                ZillowRentalIndex.yoy_change_pct.isnot(None),
            )
        )
        result = await session.execute(stmt)
        values = [row[0] for row in result.all()]

        if len(values) < 2:
            return Decimal("0.0001")

        # Calculate variance
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return max(Decimal(str(variance / 10000)), Decimal("0.0001"))  # Scale to decimal

    def _calculate_data_quality(self, record: ZillowRentalIndex) -> Decimal:
        """Calculate data quality score based on completeness."""
        quality = Decimal("1.0")

        if record.mom_change_pct is None:
            quality -= Decimal("0.1")
        if record.yoy_change_pct is None:
            quality -= Decimal("0.2")

        return max(quality, Decimal("0.5"))

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"RentInflationIndex = \frac{ZORI_{t} - ZORI_{t-12}}{ZORI_{t-12}}"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        The Rent Inflation Index captures changes in market rents that lead
        official inflation measures by approximately 12 months. Key insights:

        1. Shelter Costs: Represent ~33% of the Consumer Price Index
        2. Leading Indicator: Market rents (ZORI) lead CPI shelter components
        3. Pricing Power: Rent acceleration signals REIT pricing power
        4. Monetary Policy: Rent inflation influences Fed rate decisions

        REITs with exposure to rising rents (EQR, AVB, MAA) benefit from
        positive rent inflation, while SFR REITs (INVH, AMH) may see
        increased demand as renters are priced out of apartments.
        """


class SFRMultifamilySpread(BaseFactor):
    """Single-family vs multi-family rent differential.

    This factor captures the spread between single-family rental (SFR)
    and multi-family (apartment) rents, indicating housing preferences
    and REIT sector dynamics.

    Economic Rationale:
    - SFR premium reflects space/privacy preferences
    - Spread widening favors SFR REITs (INVH, AMH)
    - Spread narrowing favors apartment REITs (EQR, AVB, MAA)
    - Work-from-home trends influence this spread

    Formula:
    SFRMultifamilySpread = (ZORI_SFR - ZORI_MF) / ZORI_MF

    Where ZORI_SFR is single-family rent and ZORI_MF is multi-family rent.
    """

    factor_id = "sfr_multifamily_spread"
    name = "SFR-Multifamily Spread"
    description = "Single-family vs multi-family rent differential"
    domain = "real_estate"
    primary_entities = ["EQR", "AVB", "MAA", "INVH", "AMH"]

    # Factor loadings: positive for SFR REITs, negative for MF REITs
    FACTOR_LOADINGS = {
        "INVH": Decimal("1.0"),   # Invitation Homes (SFR)
        "AMH": Decimal("1.0"),    # American Homes 4 Rent (SFR)
        "EQR": Decimal("-0.5"),   # Equity Residential (MF)
        "AVB": Decimal("-0.5"),   # AvalonBay Communities (MF)
        "MAA": Decimal("-0.3"),   # Mid-America Apartment (MF, Sunbelt focus)
    }

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute SFR-Multifamily spread for given date and tickers.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers to compute for.
                    If None, compute for all primary entities.

        Returns:
            List of FactorResult objects
        """
        target_tickers = tickers or self.primary_entities
        results: list[FactorResult] = []

        async with get_async_session() as session:
            target_period = date(as_of_date.year, as_of_date.month, 1)

            # Get SFR ZORI
            sfr_record = await self._get_zori_record(
                session, target_period, "single_family"
            )

            # Get MF ZORI
            mf_record = await self._get_zori_record(
                session, target_period, "multi_family"
            )

            if not sfr_record or not mf_record:
                self.logger.warning(
                    "Missing ZORI data for spread calculation",
                    as_of_date=as_of_date,
                    has_sfr=sfr_record is not None,
                    has_mf=mf_record is not None,
                )
                return results

            # Calculate spread
            if mf_record.zori_value <= 0:
                self.logger.warning("Invalid MF ZORI value", value=mf_record.zori_value)
                return results

            spread = (sfr_record.zori_value - mf_record.zori_value) / mf_record.zori_value

            # Calculate variance from historical spreads
            variance = await self._calculate_spread_variance(session, target_period)

            # Calculate data quality
            data_quality = min(
                self._calculate_record_quality(sfr_record),
                self._calculate_record_quality(mf_record),
            )

            # Apply factor with loadings to each ticker
            for ticker in target_tickers:
                loading = self.FACTOR_LOADINGS.get(ticker, Decimal("0"))
                factor_value = spread * loading

                results.append(
                    FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=factor_value,
                        variance=variance,
                        data_quality=data_quality,
                        revision_status="original",
                        metadata={
                            "sfr_zori": float(sfr_record.zori_value),
                            "mf_zori": float(mf_record.zori_value),
                            "raw_spread": float(spread),
                            "factor_loading": float(loading),
                            "period": target_period.isoformat(),
                        },
                    )
                )

        return results

    async def _get_zori_record(
        self,
        session,
        target_period: date,
        property_type: str,
    ) -> Optional[ZillowRentalIndex]:
        """Get ZORI record for a specific period and property type."""
        stmt = (
            select(ZillowRentalIndex)
            .where(
                and_(
                    ZillowRentalIndex.period <= target_period,
                    ZillowRentalIndex.geography_level == "national",
                    ZillowRentalIndex.property_type == property_type,
                )
            )
            .order_by(ZillowRentalIndex.period.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _calculate_spread_variance(
        self,
        session,
        target_period: date,
        lookback_months: int = 12,
    ) -> Decimal:
        """Calculate variance of historical spreads."""
        # Get historical SFR and MF values
        start_period = date(
            target_period.year - 1,
            target_period.month,
            1,
        )

        # Query both property types
        stmt = select(
            ZillowRentalIndex.period,
            ZillowRentalIndex.property_type,
            ZillowRentalIndex.zori_value,
        ).where(
            and_(
                ZillowRentalIndex.period >= start_period,
                ZillowRentalIndex.period <= target_period,
                ZillowRentalIndex.geography_level == "national",
                ZillowRentalIndex.property_type.in_(["single_family", "multi_family"]),
            )
        )
        result = await session.execute(stmt)
        rows = result.all()

        # Organize by period
        by_period: dict[date, dict[str, Decimal]] = {}
        for period, prop_type, zori in rows:
            if period not in by_period:
                by_period[period] = {}
            by_period[period][prop_type] = zori

        # Calculate spreads
        spreads = []
        for period, values in by_period.items():
            if "single_family" in values and "multi_family" in values:
                mf_val = values["multi_family"]
                if mf_val > 0:
                    spread = (values["single_family"] - mf_val) / mf_val
                    spreads.append(spread)

        if len(spreads) < 2:
            return Decimal("0.0001")

        # Calculate variance
        mean = sum(spreads) / len(spreads)
        variance = sum((s - mean) ** 2 for s in spreads) / len(spreads)
        return max(Decimal(str(variance)), Decimal("0.0001"))

    def _calculate_record_quality(self, record: ZillowRentalIndex) -> Decimal:
        """Calculate data quality score for a record."""
        quality = Decimal("1.0")

        if record.mom_change_pct is None:
            quality -= Decimal("0.05")
        if record.yoy_change_pct is None:
            quality -= Decimal("0.1")

        return max(quality, Decimal("0.5"))

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"SFRMultifamilySpread = \frac{ZORI_{SFR} - ZORI_{MF}}{ZORI_{MF}} \times \beta_{ticker}"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        The SFR-Multifamily Spread captures relative preferences between
        single-family rentals and apartments. Key dynamics:

        1. Space Premium: SFR typically commands 20-40% premium over MF
        2. Work-from-Home: Remote work trends widen the spread
        3. Household Formation: Growing families prefer SFR
        4. Sector Rotation: Spread changes signal REIT sector opportunities

        Factor Loadings:
        - INVH, AMH: +1.0 (benefit from spread widening)
        - EQR, AVB: -0.5 (benefit from spread narrowing)
        - MAA: -0.3 (Sunbelt focus, partially insulated)

        A widening spread favors SFR REITs, while narrowing favors
        apartment REITs with higher density urban portfolios.
        """

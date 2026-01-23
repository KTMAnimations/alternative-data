"""Building permit factors for homebuilder and home improvement analysis."""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_session
from src.models.data_sources import BuildingPermitData
from src.transformations.factors.base import BaseFactor, FactorResult


# Primary entities: homebuilders and home improvement retailers
PRIMARY_ENTITIES = ["DHI", "LEN", "PHM", "HD", "LOW"]


class PermitMomentumFactor(BaseFactor):
    """Month-over-month change in permit volume.

    Measures the momentum in building permit issuance, which serves as
    a leading indicator for homebuilder revenue and home improvement demand.
    """

    factor_id = "permit_momentum"
    name = "Building Permit Momentum"
    description = "Month-over-month change in building permit volume"
    domain = "real_estate"
    primary_entities = PRIMARY_ENTITIES

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"\text{PermitMomentum}_t = \frac{\text{Permits}_t - \text{Permits}_{t-1}}{\text{Permits}_{t-1}} \times 100"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return (
            "Building permits are a leading indicator of construction activity. "
            "Rising permit momentum signals increasing demand for new construction, "
            "which benefits homebuilders (DHI, LEN, PHM) through increased sales volume "
            "and home improvement retailers (HD, LOW) through renovation and "
            "new home finishing materials. Permit momentum typically leads housing "
            "starts by 1-3 months and revenue recognition by 3-6 months."
        )

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute permit momentum factor.

        Args:
            as_of_date: Date to compute factor for.
            tickers: Optional list of tickers. If None, uses all primary entities.

        Returns:
            List of FactorResult objects.
        """
        target_tickers = tickers or self.primary_entities
        results = []

        async with get_async_session() as session:
            # Get permit data for current and previous month
            # Use first of month for period alignment
            current_period = as_of_date.replace(day=1)

            # Calculate previous month
            if current_period.month == 1:
                prev_period = current_period.replace(year=current_period.year - 1, month=12)
            else:
                prev_period = current_period.replace(month=current_period.month - 1)

            # Query current month national total permits
            current_query = select(BuildingPermitData).where(
                and_(
                    BuildingPermitData.period == current_period,
                    BuildingPermitData.geography_level == "national",
                    BuildingPermitData.permit_type == "total",
                    BuildingPermitData.seasonally_adjusted == True,
                )
            )
            current_result = await session.execute(current_query)
            current_data = current_result.scalar_one_or_none()

            # Query previous month
            prev_query = select(BuildingPermitData).where(
                and_(
                    BuildingPermitData.period == prev_period,
                    BuildingPermitData.geography_level == "national",
                    BuildingPermitData.permit_type == "total",
                    BuildingPermitData.seasonally_adjusted == True,
                )
            )
            prev_result = await session.execute(prev_query)
            prev_data = prev_result.scalar_one_or_none()

            if not current_data or not prev_data:
                self.logger.warning(
                    "Missing permit data for momentum calculation",
                    current_period=current_period,
                    prev_period=prev_period,
                    has_current=current_data is not None,
                    has_prev=prev_data is not None,
                )
                return results

            # Calculate momentum
            if prev_data.units_authorized > 0:
                momentum = (
                    (current_data.units_authorized - prev_data.units_authorized)
                    / prev_data.units_authorized
                )

                # Calculate variance using historical MoM changes
                variance = await self._compute_historical_variance(session, current_period)

                # Data quality based on freshness
                days_old = (date.today() - as_of_date).days
                data_quality = Decimal("1.0") if days_old <= 30 else Decimal("0.9")

                # Create result for each ticker
                for ticker in target_tickers:
                    results.append(FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal(str(round(momentum, 6))),
                        variance=variance,
                        data_quality=data_quality,
                        revision_status="original",
                        metadata={
                            "current_permits": current_data.units_authorized,
                            "prev_permits": prev_data.units_authorized,
                            "current_period": current_period.isoformat(),
                            "prev_period": prev_period.isoformat(),
                        },
                    ))

        return results

    async def _compute_historical_variance(
        self,
        session: AsyncSession,
        as_of_period: date,
        lookback_months: int = 24,
    ) -> Decimal:
        """Compute variance of MoM changes over lookback period."""
        # Get historical data
        query = select(BuildingPermitData).where(
            and_(
                BuildingPermitData.period <= as_of_period,
                BuildingPermitData.geography_level == "national",
                BuildingPermitData.permit_type == "total",
                BuildingPermitData.seasonally_adjusted == True,
                BuildingPermitData.mom_change_pct.isnot(None),
            )
        ).order_by(BuildingPermitData.period.desc()).limit(lookback_months)

        result = await session.execute(query)
        records = result.scalars().all()

        if len(records) < 2:
            return Decimal("0.01")  # Default variance

        changes = [float(r.mom_change_pct) / 100 for r in records if r.mom_change_pct]
        if not changes:
            return Decimal("0.01")

        mean = sum(changes) / len(changes)
        variance = sum((x - mean) ** 2 for x in changes) / len(changes)

        return Decimal(str(round(variance, 8)))


class PermitToStartRatioFactor(BaseFactor):
    """Ratio of building permits to housing starts.

    Measures the pipeline of future construction activity. A high ratio
    indicates permits are being issued faster than construction is starting,
    suggesting future acceleration in building activity.
    """

    factor_id = "permit_to_start_ratio"
    name = "Permit to Start Ratio"
    description = "Ratio of building permits to housing starts"
    domain = "real_estate"
    primary_entities = PRIMARY_ENTITIES

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"\text{PermitToStartRatio}_t = \frac{\text{Permits}_t}{\text{HousingStarts}_t}"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return (
            "The permit-to-start ratio captures the construction pipeline dynamics. "
            "A ratio > 1 indicates permits are outpacing starts, suggesting builders "
            "are accumulating a backlog of approved projects. This is bullish for "
            "homebuilders (DHI, LEN, PHM) as it signals strong future construction "
            "activity. For home improvement retailers (HD, LOW), a high ratio suggests "
            "sustained demand for building materials. Historical average is ~1.05."
        )

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute permit-to-start ratio factor.

        Args:
            as_of_date: Date to compute factor for.
            tickers: Optional list of tickers. If None, uses all primary entities.

        Returns:
            List of FactorResult objects.
        """
        target_tickers = tickers or self.primary_entities
        results = []

        async with get_async_session() as session:
            current_period = as_of_date.replace(day=1)

            # Query permits
            permit_query = select(BuildingPermitData).where(
                and_(
                    BuildingPermitData.period == current_period,
                    BuildingPermitData.geography_level == "national",
                    BuildingPermitData.permit_type == "total",
                    BuildingPermitData.seasonally_adjusted == True,
                )
            )
            permit_result = await session.execute(permit_query)
            permit_data = permit_result.scalar_one_or_none()

            # Query housing starts
            starts_query = select(BuildingPermitData).where(
                and_(
                    BuildingPermitData.period == current_period,
                    BuildingPermitData.geography_level == "national",
                    BuildingPermitData.permit_type == "housing_starts",
                    BuildingPermitData.seasonally_adjusted == True,
                )
            )
            starts_result = await session.execute(starts_query)
            starts_data = starts_result.scalar_one_or_none()

            if not permit_data or not starts_data:
                self.logger.warning(
                    "Missing data for permit-to-start ratio",
                    period=current_period,
                    has_permits=permit_data is not None,
                    has_starts=starts_data is not None,
                )
                return results

            # Calculate ratio
            if starts_data.units_authorized > 0:
                ratio = permit_data.units_authorized / starts_data.units_authorized

                # Calculate variance from historical ratios
                variance = await self._compute_historical_variance(session, current_period)

                # Data quality
                days_old = (date.today() - as_of_date).days
                data_quality = Decimal("1.0") if days_old <= 30 else Decimal("0.9")

                for ticker in target_tickers:
                    results.append(FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal(str(round(ratio, 6))),
                        variance=variance,
                        data_quality=data_quality,
                        revision_status="original",
                        metadata={
                            "permits": permit_data.units_authorized,
                            "housing_starts": starts_data.units_authorized,
                            "period": current_period.isoformat(),
                        },
                    ))

        return results

    async def _compute_historical_variance(
        self,
        session: AsyncSession,
        as_of_period: date,
        lookback_months: int = 24,
    ) -> Decimal:
        """Compute variance of permit-to-start ratios over lookback period."""
        # This would require a more complex query joining permits and starts
        # For now, use a reasonable default based on historical data
        return Decimal("0.005")


class RenovationShareIndexFactor(BaseFactor):
    """Index comparing renovation permits to new construction permits.

    Measures the share of construction activity going to renovations vs
    new construction. Higher values indicate more renovation activity,
    which benefits home improvement retailers.
    """

    factor_id = "renovation_share_index"
    name = "Renovation Share Index"
    description = "Ratio of renovation/improvement activity to new construction"
    domain = "real_estate"
    primary_entities = PRIMARY_ENTITIES

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"\text{RenovationShareIndex}_t = \frac{\text{MultiFamily}_t + \text{Renovation}_t}{\text{SingleFamily}_t}"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return (
            "The renovation share index captures the mix of construction activity. "
            "When new single-family construction slows (due to rates, affordability), "
            "homeowners tend to invest in renovations instead. This shift benefits "
            "home improvement retailers (HD, LOW) more than homebuilders. A rising "
            "index suggests favorable conditions for HD and LOW relative to DHI, LEN, PHM. "
            "We use multi-family permits as a proxy for renovation/improvement activity "
            "since direct renovation permit data is not consistently available."
        )

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute renovation share index factor.

        Args:
            as_of_date: Date to compute factor for.
            tickers: Optional list of tickers. If None, uses all primary entities.

        Returns:
            List of FactorResult objects.
        """
        target_tickers = tickers or self.primary_entities
        results = []

        async with get_async_session() as session:
            current_period = as_of_date.replace(day=1)

            # Query single-family permits
            sf_query = select(BuildingPermitData).where(
                and_(
                    BuildingPermitData.period == current_period,
                    BuildingPermitData.geography_level == "national",
                    BuildingPermitData.permit_type == "single_family",
                    BuildingPermitData.seasonally_adjusted == True,
                )
            )
            sf_result = await session.execute(sf_query)
            sf_data = sf_result.scalar_one_or_none()

            # Query multi-family permits (proxy for renovation/densification)
            mf_query = select(BuildingPermitData).where(
                and_(
                    BuildingPermitData.period == current_period,
                    BuildingPermitData.geography_level == "national",
                    BuildingPermitData.permit_type == "multi_family_5plus",
                    BuildingPermitData.seasonally_adjusted == True,
                )
            )
            mf_result = await session.execute(mf_query)
            mf_data = mf_result.scalar_one_or_none()

            if not sf_data or not mf_data:
                self.logger.warning(
                    "Missing data for renovation share index",
                    period=current_period,
                    has_single_family=sf_data is not None,
                    has_multi_family=mf_data is not None,
                )
                return results

            # Calculate index (multi-family / single-family ratio)
            # Higher values = more multi-family/renovation relative to new SF homes
            if sf_data.units_authorized > 0:
                index = mf_data.units_authorized / sf_data.units_authorized

                # Calculate variance
                variance = await self._compute_historical_variance(session, current_period)

                # Data quality
                days_old = (date.today() - as_of_date).days
                data_quality = Decimal("1.0") if days_old <= 30 else Decimal("0.9")

                for ticker in target_tickers:
                    # Adjust factor interpretation based on ticker type
                    # Homebuilders prefer low index (more SF construction)
                    # Home improvement benefits from high index (more renovation)
                    is_home_improvement = ticker in ["HD", "LOW"]

                    results.append(FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal(str(round(index, 6))),
                        variance=variance,
                        data_quality=data_quality,
                        revision_status="original",
                        metadata={
                            "single_family_permits": sf_data.units_authorized,
                            "multi_family_permits": mf_data.units_authorized,
                            "period": current_period.isoformat(),
                            "interpretation": (
                                "positive" if is_home_improvement else "negative"
                            ),
                        },
                    ))

        return results

    async def _compute_historical_variance(
        self,
        session: AsyncSession,
        as_of_period: date,
        lookback_months: int = 24,
    ) -> Decimal:
        """Compute variance of renovation share index over lookback period."""
        # Use a reasonable default based on historical data
        return Decimal("0.008")


# Export all factors
__all__ = [
    "PermitMomentumFactor",
    "PermitToStartRatioFactor",
    "RenovationShareIndexFactor",
    "PRIMARY_ENTITIES",
]

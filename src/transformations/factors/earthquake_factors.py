"""Earthquake-related factor computations.

Provides factors for analyzing seismic risk exposure and disaster impact
for insurance companies and related entities.

Primary Entities: ALL (Allstate), TRV (Travelers), CB (Chubb), PGR (Progressive)
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Optional

from sqlalchemy import func, select

from src.core.database import get_async_session
from src.models.data_sources import EarthquakeEvent
from src.transformations.factors.base import BaseFactor, FactorResult


# Major US population centers with coordinates and population
# Used for proximity calculations
US_POPULATION_CENTERS = {
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437, "population": 3900000},
    "San Francisco": {"lat": 37.7749, "lon": -122.4194, "population": 870000},
    "San Diego": {"lat": 32.7157, "lon": -117.1611, "population": 1400000},
    "San Jose": {"lat": 37.3382, "lon": -121.8863, "population": 1000000},
    "Seattle": {"lat": 47.6062, "lon": -122.3321, "population": 750000},
    "Portland": {"lat": 45.5152, "lon": -122.6784, "population": 650000},
    "Phoenix": {"lat": 33.4484, "lon": -112.0740, "population": 1600000},
    "Las Vegas": {"lat": 36.1699, "lon": -115.1398, "population": 640000},
    "Salt Lake City": {"lat": 40.7608, "lon": -111.8910, "population": 200000},
    "Denver": {"lat": 39.7392, "lon": -104.9903, "population": 715000},
    "Anchorage": {"lat": 61.2181, "lon": -149.9003, "population": 290000},
    "Honolulu": {"lat": 21.3069, "lon": -157.8583, "population": 350000},
}

# Insurance company headquarters and major exposure regions
INSURANCE_EXPOSURE_REGIONS = {
    "ALL": {  # Allstate - Nationwide exposure
        "name": "Allstate",
        "primary_regions": ["California", "Pacific Northwest"],
        "market_share_pct": Decimal("0.10"),  # Approximate market share
    },
    "TRV": {  # Travelers - Commercial and personal lines
        "name": "Travelers",
        "primary_regions": ["California", "Northeast"],
        "market_share_pct": Decimal("0.05"),
    },
    "CB": {  # Chubb - High-value property
        "name": "Chubb",
        "primary_regions": ["California", "Pacific Northwest", "Hawaii"],
        "market_share_pct": Decimal("0.03"),
    },
    "PGR": {  # Progressive - Auto and home
        "name": "Progressive",
        "primary_regions": ["California", "Southwest"],
        "market_share_pct": Decimal("0.08"),
    },
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers.

    Args:
        lat1, lon1: Coordinates of first point
        lat2, lon2: Coordinates of second point

    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


class SeismicRiskExposure(BaseFactor):
    """Factor measuring asset proximity to seismic events.

    Calculates weighted exposure based on:
    - Distance to earthquake epicenters
    - Earthquake magnitude
    - Population density in affected areas
    - Historical frequency in regions

    Higher values indicate greater risk exposure.

    Formula:
        SeismicRiskExposure = sum(
            (magnitude^2 / distance_km) * population_weight
        ) for each event

    Economic Rationale:
        Insurance companies with greater exposure to seismically active regions
        face higher claim risk. This factor helps quantify that exposure by
        weighing recent seismic activity against population centers where
        policies are concentrated.
    """

    factor_id: str = "seismic_risk_exposure"
    name: str = "Seismic Risk Exposure"
    description: str = "Measures asset proximity to recent seismic events"
    domain: str = "insurance"
    primary_entities: list[str] = ["ALL", "TRV", "CB", "PGR"]

    # Configuration
    LOOKBACK_DAYS: int = 30
    MAX_DISTANCE_KM: float = 500.0  # Events beyond this are not considered
    MAGNITUDE_EXPONENT: float = 2.0  # Exponential scaling for magnitude
    BASELINE_EXPOSURE: Decimal = Decimal("0.001")  # Minimum exposure level

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute seismic risk exposure for insurance tickers.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (default: all primary entities)

        Returns:
            List of FactorResult objects
        """
        target_tickers = tickers or self.primary_entities
        results = []

        # Fetch recent earthquake events
        events = await self._get_recent_events(as_of_date)

        if not events:
            # No seismic activity - return baseline exposure
            for ticker in target_tickers:
                results.append(
                    FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=self.BASELINE_EXPOSURE,
                        variance=Decimal("0.0001"),
                        data_quality=Decimal("0.5"),  # Lower quality without events
                        metadata={"event_count": 0, "reason": "no_recent_events"},
                    )
                )
            return results

        for ticker in target_tickers:
            try:
                exposure = await self._calculate_exposure(ticker, events)
                variance = await self._calculate_variance(ticker, events)

                results.append(
                    FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=exposure,
                        variance=variance,
                        data_quality=Decimal("0.95"),
                        metadata={
                            "event_count": len(events),
                            "max_magnitude": float(max(e.magnitude for e in events)),
                            "regions_affected": self._get_affected_regions(events),
                        },
                    )
                )
            except Exception as e:
                self.logger.error(
                    "Error computing exposure",
                    ticker=ticker,
                    error=str(e),
                )
                continue

        return results

    async def _get_recent_events(self, as_of_date: date) -> list[EarthquakeEvent]:
        """Fetch earthquake events from the lookback window."""
        async with get_async_session() as session:
            start_date = datetime.combine(
                as_of_date - timedelta(days=self.LOOKBACK_DAYS),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            end_date = datetime.combine(
                as_of_date,
                datetime.max.time(),
                tzinfo=timezone.utc,
            )

            query = (
                select(EarthquakeEvent)
                .where(EarthquakeEvent.timestamp >= start_date)
                .where(EarthquakeEvent.timestamp <= end_date)
                .where(EarthquakeEvent.magnitude >= Decimal("4.0"))
                .order_by(EarthquakeEvent.magnitude.desc())
            )

            result = await session.execute(query)
            return list(result.scalars().all())

    async def _calculate_exposure(
        self,
        ticker: str,
        events: list[EarthquakeEvent],
    ) -> Decimal:
        """Calculate total exposure for a ticker based on events."""
        exposure_info = INSURANCE_EXPOSURE_REGIONS.get(ticker)
        if not exposure_info:
            return self.BASELINE_EXPOSURE

        total_exposure = Decimal("0")

        for event in events:
            event_lat = float(event.latitude)
            event_lon = float(event.longitude)

            # Calculate exposure based on proximity to population centers
            for city, city_info in US_POPULATION_CENTERS.items():
                distance = haversine_distance(
                    event_lat, event_lon,
                    city_info["lat"], city_info["lon"],
                )

                if distance <= self.MAX_DISTANCE_KM:
                    # Magnitude-weighted, distance-decayed exposure
                    magnitude_factor = float(event.magnitude) ** self.MAGNITUDE_EXPONENT
                    distance_factor = max(1, distance)  # Avoid division by zero
                    population_weight = city_info["population"] / 1_000_000  # Millions

                    event_exposure = (
                        magnitude_factor / distance_factor
                    ) * population_weight * float(exposure_info["market_share_pct"])

                    total_exposure += Decimal(str(event_exposure))

        # Normalize to reasonable scale (0 to 1)
        normalized_exposure = min(
            max(total_exposure / Decimal("100"), self.BASELINE_EXPOSURE),
            Decimal("1.0"),
        )

        return normalized_exposure.quantize(Decimal("0.0001"))

    async def _calculate_variance(
        self,
        ticker: str,
        events: list[EarthquakeEvent],
    ) -> Decimal:
        """Calculate variance in exposure estimates."""
        if len(events) < 2:
            return Decimal("0.0001")

        # Calculate variance based on magnitude distribution
        magnitudes = [float(e.magnitude) for e in events]
        mean_mag = sum(magnitudes) / len(magnitudes)
        variance = sum((m - mean_mag) ** 2 for m in magnitudes) / len(magnitudes)

        return Decimal(str(min(variance / 100, 0.1))).quantize(Decimal("0.0001"))

    def _get_affected_regions(self, events: list[EarthquakeEvent]) -> list[str]:
        """Identify geographic regions affected by events."""
        regions = set()

        for event in events:
            lat = float(event.latitude)
            lon = float(event.longitude)

            # Simple region classification
            if lat >= 32 and lat <= 42 and lon >= -125 and lon <= -114:
                regions.add("California")
            if lat >= 42 and lat <= 49 and lon >= -125 and lon <= -116:
                regions.add("Pacific Northwest")
            if lat >= 18 and lat <= 23 and lon >= -161 and lon <= -154:
                regions.add("Hawaii")
            if lat >= 51 and lat <= 72 and lon >= -170 and lon <= -130:
                regions.add("Alaska")

        return list(regions)

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"""
        \text{SeismicRiskExposure} = \sum_{e \in E} \frac{M_e^{2}}{D_e} \cdot P_w \cdot S_m

        \text{where:}
        \begin{align}
        E &= \text{set of earthquake events in lookback window} \\
        M_e &= \text{magnitude of event } e \\
        D_e &= \text{distance from event to population center (km)} \\
        P_w &= \text{population weight (millions)} \\
        S_m &= \text{market share percentage}
        \end{align}
        """

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        Insurance companies face material claim risk from seismic events. This factor
        quantifies that risk by:

        1. **Magnitude Scaling**: Uses magnitude^2 to reflect the exponential increase
           in damage potential with larger earthquakes.

        2. **Distance Decay**: Risk decreases with distance from the epicenter,
           following established seismological principles.

        3. **Population Weighting**: Areas with higher population density represent
           greater insured exposure and potential claims volume.

        4. **Market Share**: Companies with larger market shares in affected regions
           face proportionally higher claim risk.

        Investment signals:
        - High exposure values may indicate elevated claim reserves needed
        - Sudden spikes suggest near-term earnings pressure from catastrophe losses
        - Regional concentration reveals geographic risk concentration
        """


class DisasterImpactEstimate(BaseFactor):
    """Factor estimating economic damage and insurer loss from seismic events.

    Combines multiple models to estimate:
    - Direct economic damage (property, infrastructure)
    - Insurance industry loss distribution
    - Company-specific loss estimates based on market share

    Higher values indicate greater estimated losses.

    Formula:
        DisasterImpact = EconomicDamage * InsuredPct * MarketShare * LossRatio

    Economic Rationale:
        Catastrophe losses directly impact insurance company earnings and
        capital adequacy. This factor provides a real-time estimate of
        potential losses to inform trading decisions around earnings risk.
    """

    factor_id: str = "disaster_impact_estimate"
    name: str = "Disaster Impact Estimate"
    description: str = "Estimates economic damage and insurer loss from seismic events"
    domain: str = "insurance"
    primary_entities: list[str] = ["ALL", "TRV", "CB", "PGR"]

    # Economic model parameters
    LOOKBACK_DAYS: int = 7  # Shorter window for immediate impact
    INSURED_PCT: Decimal = Decimal("0.15")  # ~15% of economic damage typically insured
    BASE_DAMAGE_MULTIPLIER: Decimal = Decimal("10000000")  # Base $ per magnitude unit
    LOSS_RATIO_ESTIMATE: Decimal = Decimal("0.75")  # Expected loss ratio on claims

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute disaster impact estimates for insurance tickers.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (default: all primary entities)

        Returns:
            List of FactorResult objects
        """
        target_tickers = tickers or self.primary_entities
        results = []

        # Fetch recent significant events
        events = await self._get_significant_events(as_of_date)

        if not events:
            # No significant events - return zero impact
            for ticker in target_tickers:
                results.append(
                    FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal("0"),
                        variance=Decimal("0"),
                        data_quality=Decimal("0.9"),
                        metadata={"event_count": 0, "reason": "no_significant_events"},
                    )
                )
            return results

        # Calculate total economic damage estimate
        total_damage = await self._estimate_total_damage(events)

        for ticker in target_tickers:
            try:
                loss_estimate = await self._estimate_company_loss(
                    ticker, total_damage, events
                )
                variance = self._estimate_variance(loss_estimate, events)

                results.append(
                    FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=loss_estimate,
                        variance=variance,
                        data_quality=Decimal("0.85"),
                        metadata={
                            "event_count": len(events),
                            "total_economic_damage_usd": float(total_damage),
                            "industry_insured_loss_usd": float(
                                total_damage * self.INSURED_PCT
                            ),
                            "most_severe_event": max(
                                events, key=lambda e: e.magnitude
                            ).event_id,
                        },
                    )
                )
            except Exception as e:
                self.logger.error(
                    "Error computing disaster impact",
                    ticker=ticker,
                    error=str(e),
                )
                continue

        return results

    async def _get_significant_events(self, as_of_date: date) -> list[EarthquakeEvent]:
        """Fetch significant earthquake events (magnitude >= 5.0)."""
        async with get_async_session() as session:
            start_date = datetime.combine(
                as_of_date - timedelta(days=self.LOOKBACK_DAYS),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            end_date = datetime.combine(
                as_of_date,
                datetime.max.time(),
                tzinfo=timezone.utc,
            )

            query = (
                select(EarthquakeEvent)
                .where(EarthquakeEvent.timestamp >= start_date)
                .where(EarthquakeEvent.timestamp <= end_date)
                .where(EarthquakeEvent.magnitude >= Decimal("5.0"))
                .order_by(EarthquakeEvent.magnitude.desc())
            )

            result = await session.execute(query)
            return list(result.scalars().all())

    async def _estimate_total_damage(
        self,
        events: list[EarthquakeEvent],
    ) -> Decimal:
        """Estimate total economic damage from events.

        Uses simplified damage model based on:
        - Magnitude (exponential scaling)
        - Population exposure
        - Depth (shallow = more damage)
        """
        total_damage = Decimal("0")

        for event in events:
            # Base damage from magnitude (exponential relationship)
            magnitude = float(event.magnitude)
            magnitude_factor = Decimal(str(10 ** (magnitude - 4)))  # Normalize to M4 baseline

            # Depth adjustment (shallower = more damage)
            depth_km = max(float(event.depth_km), 1)
            depth_factor = Decimal(str(min(100 / depth_km, 5)))  # Cap at 5x

            # Population exposure from USGS if available
            pop_exposure = event.estimated_population_exposure or 1000
            pop_factor = Decimal(str(min(pop_exposure / 10000, 10)))  # Normalize

            event_damage = (
                self.BASE_DAMAGE_MULTIPLIER
                * magnitude_factor
                * depth_factor
                * pop_factor
            )

            total_damage += event_damage

        return total_damage.quantize(Decimal("1"))

    async def _estimate_company_loss(
        self,
        ticker: str,
        total_damage: Decimal,
        events: list[EarthquakeEvent],
    ) -> Decimal:
        """Estimate company-specific loss based on market share.

        Args:
            ticker: Company ticker symbol
            total_damage: Total economic damage estimate
            events: List of earthquake events

        Returns:
            Estimated company loss in USD (normalized to millions)
        """
        exposure_info = INSURANCE_EXPOSURE_REGIONS.get(ticker)
        if not exposure_info:
            return Decimal("0")

        # Calculate industry insured loss
        industry_loss = total_damage * self.INSURED_PCT * self.LOSS_RATIO_ESTIMATE

        # Company share based on market share
        company_loss = industry_loss * exposure_info["market_share_pct"]

        # Normalize to millions for factor values
        normalized_loss = company_loss / Decimal("1000000")

        return normalized_loss.quantize(Decimal("0.01"))

    def _estimate_variance(
        self,
        loss_estimate: Decimal,
        events: list[EarthquakeEvent],
    ) -> Decimal:
        """Estimate uncertainty in loss estimate.

        Higher variance for:
        - Larger events (more uncertainty)
        - Multiple events (compounding uncertainty)
        """
        if loss_estimate == 0:
            return Decimal("0")

        # Base variance as percentage of estimate
        base_variance = float(loss_estimate) * 0.3  # 30% base uncertainty

        # Add uncertainty for event count
        event_factor = 1 + (len(events) - 1) * 0.1

        # Add uncertainty for high magnitude events
        max_magnitude = max(float(e.magnitude) for e in events)
        magnitude_factor = 1 + (max_magnitude - 5) * 0.2 if max_magnitude > 5 else 1

        variance = base_variance * event_factor * magnitude_factor

        return Decimal(str(variance)).quantize(Decimal("0.01"))

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"""
        \text{DisasterImpact} = D_{total} \cdot I_{pct} \cdot L_r \cdot S_m

        \text{where:}
        \begin{align}
        D_{total} &= \sum_{e \in E} B \cdot 10^{(M_e - 4)} \cdot \frac{100}{d_e} \cdot P_e \\
        I_{pct} &= \text{insured percentage (15\%)} \\
        L_r &= \text{loss ratio (75\%)} \\
        S_m &= \text{company market share} \\
        B &= \text{base damage multiplier (\$10M)} \\
        M_e &= \text{magnitude of event } e \\
        d_e &= \text{depth in km} \\
        P_e &= \text{population exposure factor}
        \end{align}
        """

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        Catastrophe losses can materially impact insurance company earnings and
        capital positions. This factor estimates potential losses by:

        1. **Economic Damage Model**: Estimates total economic damage using
           established relationships between magnitude, depth, and population
           exposure. Larger, shallower events near populated areas cause
           more damage.

        2. **Insurance Loss Distribution**: Only ~15% of economic damage is
           typically covered by insurance. We apply this ratio and assume
           a 75% loss ratio (claims paid / premiums earned).

        3. **Market Share Attribution**: Company-specific losses are estimated
           based on their market share in affected regions.

        Investment signals:
        - Values > $100M suggest material quarterly earnings impact
        - Values > $500M may affect capital adequacy ratios
        - Compare to company catastrophe loss budgets for relative impact
        - Use for relative value trades between affected/unaffected insurers
        """

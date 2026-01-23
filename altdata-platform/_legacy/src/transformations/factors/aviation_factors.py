"""Aviation-derived factor computations from ADS-B data."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from haversine import haversine, Unit
from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.adsb import Aircraft, FlightPosition, FlightLanding, CompanyHQ
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_executive_flight_frequency(
    company_id: str,
    start_date: datetime,
    end_date: datetime,
) -> float:
    """Calculate number of flights per week for company jets.

    Args:
        company_id: Company entity ID
        start_date: Period start
        end_date: Period end

    Returns:
        Flights per week
    """
    session = SessionLocal()
    try:
        flights = (
            session.query(FlightLanding)
            .join(Aircraft)
            .filter(
                Aircraft.company_entity_id == company_id,
                FlightLanding.landing_timestamp >= start_date,
                FlightLanding.landing_timestamp <= end_date,
            )
            .count()
        )

        weeks = (end_date - start_date).days / 7
        return flights / weeks if weeks > 0 else 0.0
    finally:
        session.close()


def calc_hq_visit_score(
    source_company: str,
    target_company: str,
    start_date: datetime,
    end_date: datetime,
) -> float:
    """Calculate frequency of jets landing near another company's HQ.

    A high score may indicate M&A discussions or partnership talks.

    Args:
        source_company: Company whose jets are being tracked
        target_company: Company whose HQ is being visited
        start_date: Period start
        end_date: Period end

    Returns:
        Visit frequency score (visits / total landings)
    """
    session = SessionLocal()
    try:
        # Get target company HQ coordinates
        target_hq = session.query(CompanyHQ).filter_by(
            entity_id=target_company
        ).first()

        if not target_hq:
            return 0.0

        target_coords = (target_hq.latitude, target_hq.longitude)

        # Get all landings of source company jets
        landings = (
            session.query(FlightLanding)
            .join(Aircraft)
            .filter(
                Aircraft.company_entity_id == source_company,
                FlightLanding.landing_timestamp >= start_date,
                FlightLanding.landing_timestamp <= end_date,
            )
            .all()
        )

        if not landings:
            return 0.0

        # Count landings within 50km of target HQ
        visits = 0
        for landing in landings:
            if landing.latitude and landing.longitude:
                landing_coords = (landing.latitude, landing.longitude)
                distance = haversine(landing_coords, target_coords, unit=Unit.KILOMETERS)
                if distance < 50:
                    visits += 1

        return visits / len(landings)
    finally:
        session.close()


def calc_unusual_destination_alert(
    current_landing: Dict,
    historical_landings: List[Dict],
    threshold_km: float = 20
) -> int:
    """Check if jet visited location not visited in prior period.

    Unusual destinations may signal new business relationships
    or M&A activity.

    Args:
        current_landing: Current landing location dict
        historical_landings: List of prior landing locations
        threshold_km: Distance to consider "same" location

    Returns:
        1 if unusual destination, 0 if known
    """
    if not current_landing.get("latitude") or not current_landing.get("longitude"):
        return 0

    current_dest = (current_landing["latitude"], current_landing["longitude"])

    for hist in historical_landings:
        if hist.get("latitude") and hist.get("longitude"):
            hist_dest = (hist["latitude"], hist["longitude"])
            distance = haversine(current_dest, hist_dest, unit=Unit.KILOMETERS)
            if distance < threshold_km:
                return 0  # Been here before

    return 1  # New destination


def calc_multi_company_colocation(
    airport_icao: str,
    timestamp: datetime,
    window_hours: int = 24,
) -> int:
    """Count companies with jets at same airport within time window.

    High colocation may indicate private meetings or conferences.

    Args:
        airport_icao: Airport ICAO code
        timestamp: Reference timestamp
        window_hours: Time window in hours

    Returns:
        Number of unique companies
    """
    session = SessionLocal()
    try:
        start = timestamp - timedelta(hours=window_hours)
        end = timestamp + timedelta(hours=window_hours)

        landings = (
            session.query(FlightLanding)
            .join(Aircraft)
            .filter(
                FlightLanding.airport_icao == airport_icao,
                FlightLanding.landing_timestamp >= start,
                FlightLanding.landing_timestamp <= end,
                Aircraft.company_entity_id.isnot(None),
            )
            .all()
        )

        companies = set(l.aircraft.company_entity_id for l in landings if l.aircraft)
        return len(companies)
    finally:
        session.close()


@FactorRegistry.register
class ExecutiveFlightFrequency(BaseFactor):
    """Executive Flight Frequency Factor.

    Measures corporate jet activity as proxy for executive
    travel and business activity.
    """

    FACTOR_NAME = "executive_flight_frequency"
    FACTOR_DESCRIPTION = "Weekly corporate jet flight frequency"
    CATEGORY = "aviation"
    ENTITY_TYPE = "company"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 28

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: Optional[int] = None,
    ) -> Optional[float]:
        """Compute flight frequency for company.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_days: Override default lookback

        Returns:
            Flights per week
        """
        lookback = lookback_days or self.LOOKBACK_DAYS
        start_date = as_of_date - timedelta(days=lookback)

        return calc_executive_flight_frequency(entity_id, start_date, as_of_date)


@FactorRegistry.register
class HQVisitScore(BaseFactor):
    """HQ Visit Score Factor.

    Measures frequency of corporate jets visiting other
    companies' headquarters - potential M&A signal.
    """

    FACTOR_NAME = "hq_visit_score"
    FACTOR_DESCRIPTION = "Frequency of jets landing near target company HQ"
    CATEGORY = "aviation"
    ENTITY_TYPE = "company_pair"  # Requires source and target
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 90

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        target_company: Optional[str] = None,
        lookback_days: Optional[int] = None,
    ) -> Optional[float]:
        """Compute HQ visit score.

        Args:
            entity_id: Source company (whose jets are tracked)
            as_of_date: Date for computation
            target_company: Target company HQ to monitor
            lookback_days: Override default lookback

        Returns:
            Visit score (0-1)
        """
        if not target_company:
            return None

        lookback = lookback_days or self.LOOKBACK_DAYS
        start_date = as_of_date - timedelta(days=lookback)

        return calc_hq_visit_score(entity_id, target_company, start_date, as_of_date)


@FactorRegistry.register
class UnusualDestinationAlert(BaseFactor):
    """Unusual Destination Alert Factor.

    Binary signal when corporate jet visits location
    not visited in prior 12 months.
    """

    FACTOR_NAME = "unusual_destination_alert"
    FACTOR_DESCRIPTION = "Flag for new destinations not visited in 12 months"
    CATEGORY = "aviation"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 365

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: Optional[int] = None,
    ) -> Optional[float]:
        """Compute unusual destination alert.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_days: Override default lookback

        Returns:
            1.0 if unusual destination, 0.0 otherwise
        """
        lookback = lookback_days or self.LOOKBACK_DAYS
        start_date = as_of_date - timedelta(days=lookback)

        session = self._get_session()
        try:
            # Get most recent landing
            recent = (
                session.query(FlightLanding)
                .join(Aircraft)
                .filter(
                    Aircraft.company_entity_id == entity_id,
                    FlightLanding.landing_timestamp <= as_of_date,
                )
                .order_by(FlightLanding.landing_timestamp.desc())
                .first()
            )

            if not recent:
                return 0.0

            current_landing = {
                "latitude": recent.latitude,
                "longitude": recent.longitude,
            }

            # Get historical landings (excluding most recent day)
            historical = (
                session.query(FlightLanding)
                .join(Aircraft)
                .filter(
                    Aircraft.company_entity_id == entity_id,
                    FlightLanding.landing_timestamp >= start_date,
                    FlightLanding.landing_timestamp < as_of_date - timedelta(days=1),
                )
                .all()
            )

            historical_landings = [
                {"latitude": l.latitude, "longitude": l.longitude}
                for l in historical
            ]

            return float(calc_unusual_destination_alert(current_landing, historical_landings))

        finally:
            self._close_session()


@FactorRegistry.register
class MultiCompanyColocation(BaseFactor):
    """Multi-Company Colocation Factor.

    Count of companies with jets at same airport
    within 24-hour window.
    """

    FACTOR_NAME = "multi_company_colocation"
    FACTOR_DESCRIPTION = "Companies with jets at same airport within 24h"
    CATEGORY = "aviation"
    ENTITY_TYPE = "airport"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,  # Airport ICAO code
        as_of_date: datetime,
        window_hours: int = 24,
    ) -> Optional[float]:
        """Compute colocation count.

        Args:
            entity_id: Airport ICAO code
            as_of_date: Date for computation
            window_hours: Time window

        Returns:
            Number of unique companies
        """
        return float(calc_multi_company_colocation(entity_id, as_of_date, window_hours))

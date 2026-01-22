"""Patent-derived factor computations."""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.patents import Patent, PatentAssignee, PatentApplication
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_patent_momentum(
    entity_id: str,
    as_of_date: date,
    current_period_days: int = 90,
    prior_period_days: int = 90,
) -> Optional[float]:
    """Calculate patent filing momentum (current vs prior period).

    Positive momentum indicates accelerating innovation.

    Args:
        entity_id: Company entity ID
        as_of_date: Reference date
        current_period_days: Days in current period
        prior_period_days: Days in prior period

    Returns:
        Momentum score (current - prior) / prior * 100
    """
    session = SessionLocal()
    try:
        # Current period
        current_start = as_of_date - timedelta(days=current_period_days)
        current_count = (
            session.query(func.count(Patent.id))
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == entity_id,
                Patent.grant_date >= current_start,
                Patent.grant_date <= as_of_date,
            )
            .scalar()
        ) or 0

        # Prior period
        prior_end = current_start - timedelta(days=1)
        prior_start = prior_end - timedelta(days=prior_period_days)
        prior_count = (
            session.query(func.count(Patent.id))
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == entity_id,
                Patent.grant_date >= prior_start,
                Patent.grant_date <= prior_end,
            )
            .scalar()
        ) or 0

        if prior_count == 0:
            return float(current_count) if current_count > 0 else None

        return ((current_count - prior_count) / prior_count) * 100
    finally:
        session.close()


def calc_innovation_velocity(
    entity_id: str,
    as_of_date: date,
    lookback_days: int = 365,
) -> Optional[float]:
    """Calculate patent grants per month over lookback period.

    Args:
        entity_id: Company entity ID
        as_of_date: Reference date
        lookback_days: Days to look back

    Returns:
        Average patents per month
    """
    session = SessionLocal()
    try:
        start_date = as_of_date - timedelta(days=lookback_days)

        count = (
            session.query(func.count(Patent.id))
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == entity_id,
                Patent.grant_date >= start_date,
                Patent.grant_date <= as_of_date,
            )
            .scalar()
        ) or 0

        months = lookback_days / 30.0
        return count / months if months > 0 else 0.0
    finally:
        session.close()


def calc_patent_quality_score(
    entity_id: str,
    as_of_date: date,
    lookback_days: int = 365,
) -> Optional[float]:
    """Calculate average claims per patent as quality proxy.

    More claims generally indicates broader protection.

    Args:
        entity_id: Company entity ID
        as_of_date: Reference date
        lookback_days: Days to look back

    Returns:
        Average claims per patent
    """
    session = SessionLocal()
    try:
        start_date = as_of_date - timedelta(days=lookback_days)

        avg_claims = (
            session.query(func.avg(Patent.claims_count))
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == entity_id,
                Patent.grant_date >= start_date,
                Patent.grant_date <= as_of_date,
                Patent.claims_count.isnot(None),
            )
            .scalar()
        )

        return float(avg_claims) if avg_claims else None
    finally:
        session.close()


def calc_technology_diversity(
    entity_id: str,
    as_of_date: date,
    lookback_days: int = 365,
) -> Optional[float]:
    """Calculate diversity of patent classifications.

    Higher diversity indicates broader R&D portfolio.

    Args:
        entity_id: Company entity ID
        as_of_date: Reference date
        lookback_days: Days to look back

    Returns:
        Number of unique CPC classes
    """
    session = SessionLocal()
    try:
        start_date = as_of_date - timedelta(days=lookback_days)

        unique_classes = (
            session.query(func.count(func.distinct(Patent.primary_class)))
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == entity_id,
                Patent.grant_date >= start_date,
                Patent.grant_date <= as_of_date,
                Patent.primary_class.isnot(None),
            )
            .scalar()
        )

        return float(unique_classes) if unique_classes else None
    finally:
        session.close()


def calc_time_to_grant(
    entity_id: str,
    as_of_date: date,
    lookback_days: int = 365,
) -> Optional[float]:
    """Calculate average days from filing to grant.

    Shorter times may indicate patent quality or USPTO prioritization.

    Args:
        entity_id: Company entity ID
        as_of_date: Reference date
        lookback_days: Days to look back

    Returns:
        Average days to grant
    """
    session = SessionLocal()
    try:
        start_date = as_of_date - timedelta(days=lookback_days)

        patents = (
            session.query(Patent)
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == entity_id,
                Patent.grant_date >= start_date,
                Patent.grant_date <= as_of_date,
                Patent.filing_date.isnot(None),
                Patent.grant_date.isnot(None),
            )
            .all()
        )

        if not patents:
            return None

        total_days = 0
        count = 0
        for patent in patents:
            if patent.filing_date and patent.grant_date:
                days = (patent.grant_date - patent.filing_date).days
                if days > 0:
                    total_days += days
                    count += 1

        return total_days / count if count > 0 else None
    finally:
        session.close()


@FactorRegistry.register
class PatentMomentum(BaseFactor):
    """Patent Momentum Factor.

    Measures acceleration/deceleration in patent activity
    compared to prior period.
    """

    FACTOR_NAME = "patent_momentum"
    FACTOR_DESCRIPTION = "Patent filing rate change vs prior period"
    CATEGORY = "patents"
    ENTITY_TYPE = "company"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 90

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        current_period_days: int = 90,
        prior_period_days: int = 90,
    ) -> Optional[float]:
        """Compute patent momentum.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            current_period_days: Current period length
            prior_period_days: Prior period length

        Returns:
            Momentum percentage
        """
        ref_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_patent_momentum(
            entity_id, ref_date, current_period_days, prior_period_days
        )


@FactorRegistry.register
class InnovationVelocity(BaseFactor):
    """Innovation Velocity Factor.

    Average patents granted per month as innovation rate.
    """

    FACTOR_NAME = "innovation_velocity"
    FACTOR_DESCRIPTION = "Average patents granted per month"
    CATEGORY = "patents"
    ENTITY_TYPE = "company"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 365

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 365,
    ) -> Optional[float]:
        """Compute innovation velocity.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_days: Lookback period

        Returns:
            Patents per month
        """
        ref_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_innovation_velocity(entity_id, ref_date, lookback_days)


@FactorRegistry.register
class PatentQualityScore(BaseFactor):
    """Patent Quality Score Factor.

    Average claims per patent as quality indicator.
    """

    FACTOR_NAME = "patent_quality_score"
    FACTOR_DESCRIPTION = "Average claims per patent"
    CATEGORY = "patents"
    ENTITY_TYPE = "company"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 365

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 365,
    ) -> Optional[float]:
        """Compute patent quality score.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_days: Lookback period

        Returns:
            Average claims per patent
        """
        ref_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_patent_quality_score(entity_id, ref_date, lookback_days)


@FactorRegistry.register
class TechnologyDiversity(BaseFactor):
    """Technology Diversity Factor.

    Number of unique patent classifications indicating R&D breadth.
    """

    FACTOR_NAME = "technology_diversity"
    FACTOR_DESCRIPTION = "Number of unique patent classifications"
    CATEGORY = "patents"
    ENTITY_TYPE = "company"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 365

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 365,
    ) -> Optional[float]:
        """Compute technology diversity.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_days: Lookback period

        Returns:
            Unique class count
        """
        ref_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_technology_diversity(entity_id, ref_date, lookback_days)


@FactorRegistry.register
class TimeToGrant(BaseFactor):
    """Time to Grant Factor.

    Average days from filing to patent grant.
    """

    FACTOR_NAME = "time_to_grant"
    FACTOR_DESCRIPTION = "Average days from filing to grant"
    CATEGORY = "patents"
    ENTITY_TYPE = "company"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 365

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 365,
    ) -> Optional[float]:
        """Compute time to grant.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_days: Lookback period

        Returns:
            Average days to grant
        """
        ref_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_time_to_grant(entity_id, ref_date, lookback_days)


def calc_patent_grant_rate(
    entity_id: str,
    as_of_date: date,
    lookback_days: int = 730,  # 2 years for applications -> grants cycle
) -> Optional[float]:
    """Calculate patent grant rate (grants / applications).

    Higher rates may indicate higher quality patent filings.

    Args:
        entity_id: Company entity ID
        as_of_date: Reference date
        lookback_days: Days to look back

    Returns:
        Grant rate as percentage (0-100)
    """
    session = SessionLocal()
    try:
        start_date = as_of_date - timedelta(days=lookback_days)

        # Count grants
        grants = (
            session.query(func.count(Patent.id))
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == entity_id,
                Patent.grant_date >= start_date,
                Patent.grant_date <= as_of_date,
            )
            .scalar()
        ) or 0

        # Count applications
        applications = (
            session.query(func.count(PatentApplication.id))
            .filter(
                PatentApplication.assignee_id == entity_id,
                PatentApplication.filing_date >= start_date,
                PatentApplication.filing_date <= as_of_date,
            )
            .scalar()
        ) or 0

        if applications == 0:
            return None

        return (grants / applications) * 100
    finally:
        session.close()


def calc_patent_breadth_index(
    entity_id: str,
    as_of_date: date,
    lookback_days: int = 365,
) -> Optional[float]:
    """Calculate patent breadth index (CPC code diversity).

    More diverse CPC codes indicate broader R&D portfolio
    and potentially more innovative capacity.

    Args:
        entity_id: Company entity ID
        as_of_date: Reference date
        lookback_days: Days to look back

    Returns:
        Number of unique CPC top-level classes
    """
    session = SessionLocal()
    try:
        start_date = as_of_date - timedelta(days=lookback_days)

        # Get unique CPC classes (just the section letter for diversity)
        patents = (
            session.query(Patent.primary_class)
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == entity_id,
                Patent.grant_date >= start_date,
                Patent.grant_date <= as_of_date,
                Patent.primary_class.isnot(None),
            )
            .distinct()
            .all()
        )

        if not patents:
            return None

        # Extract unique top-level classes (e.g., "H04L" -> "H")
        unique_sections = set()
        for (cpc_class,) in patents:
            if cpc_class and len(cpc_class) > 0:
                # Get the section (first character) and class (first 3 chars)
                unique_sections.add(cpc_class[:3] if len(cpc_class) >= 3 else cpc_class)

        return float(len(unique_sections))
    finally:
        session.close()


def calc_inventor_retention(
    entity_id: str,
    as_of_date: date,
    lookback_days: int = 730,  # 2 years
) -> Optional[float]:
    """Calculate inventor retention rate.

    Percentage of inventors with multiple patents for the company.
    Higher retention may indicate better R&D culture.

    Args:
        entity_id: Company entity ID
        as_of_date: Reference date
        lookback_days: Days to look back

    Returns:
        Retention rate as percentage
    """
    session = SessionLocal()
    try:
        from src.models.patents import PatentInventor

        start_date = as_of_date - timedelta(days=lookback_days)

        # Get all inventors for this company's patents
        inventor_counts = (
            session.query(
                PatentInventor.inventor_name,
                func.count(PatentInventor.id).label('patent_count')
            )
            .join(Patent, PatentInventor.patent_number == Patent.patent_number)
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == entity_id,
                Patent.grant_date >= start_date,
                Patent.grant_date <= as_of_date,
            )
            .group_by(PatentInventor.inventor_name)
            .all()
        )

        if not inventor_counts:
            return None

        total_inventors = len(inventor_counts)
        repeat_inventors = sum(1 for _, count in inventor_counts if count > 1)

        return (repeat_inventors / total_inventors) * 100
    finally:
        session.close()


def calc_r_and_d_intensity_proxy(
    entity_id: str,
    as_of_date: date,
    lookback_days: int = 365,
) -> Optional[float]:
    """Calculate R&D intensity proxy from patent activity.

    Patents per quarter normalized by company size proxy.
    Higher values indicate more R&D intensive operations.

    Args:
        entity_id: Company entity ID
        as_of_date: Reference date
        lookback_days: Days to look back

    Returns:
        Patents per quarter (as R&D proxy)
    """
    session = SessionLocal()
    try:
        start_date = as_of_date - timedelta(days=lookback_days)

        count = (
            session.query(func.count(Patent.id))
            .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
            .filter(
                PatentAssignee.entity_id == entity_id,
                Patent.grant_date >= start_date,
                Patent.grant_date <= as_of_date,
            )
            .scalar()
        ) or 0

        # Return patents per quarter
        quarters = lookback_days / 90.0
        return count / quarters if quarters > 0 else 0.0
    finally:
        session.close()


@FactorRegistry.register
class PatentGrantRate(BaseFactor):
    """Patent Grant Rate Factor.

    Ratio of granted patents to applications filed.
    Higher rates may indicate patent quality.
    """

    FACTOR_NAME = "patent_grant_rate"
    FACTOR_DESCRIPTION = "Patent grants as percentage of applications"
    CATEGORY = "patents"
    ENTITY_TYPE = "company"
    FREQUENCY = "quarterly"
    LOOKBACK_DAYS = 730

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 730,
    ) -> Optional[float]:
        """Compute patent grant rate.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_days: Lookback period

        Returns:
            Grant rate percentage
        """
        ref_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_patent_grant_rate(entity_id, ref_date, lookback_days)


@FactorRegistry.register
class PatentBreadthIndex(BaseFactor):
    """Patent Breadth Index Factor.

    Diversity of CPC classifications in patent portfolio.
    Higher values indicate broader R&D coverage.
    """

    FACTOR_NAME = "patent_breadth_index"
    FACTOR_DESCRIPTION = "Diversity of patent classification codes"
    CATEGORY = "patents"
    ENTITY_TYPE = "company"
    FREQUENCY = "quarterly"
    LOOKBACK_DAYS = 365

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 365,
    ) -> Optional[float]:
        """Compute patent breadth index.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_days: Lookback period

        Returns:
            Unique CPC class count
        """
        ref_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_patent_breadth_index(entity_id, ref_date, lookback_days)


@FactorRegistry.register
class RAndDIntensityProxy(BaseFactor):
    """R&D Intensity Proxy Factor.

    Patent activity normalized by time as R&D investment proxy.
    Higher values indicate more R&D intensive companies.
    """

    FACTOR_NAME = "r_and_d_intensity_proxy"
    FACTOR_DESCRIPTION = "Patents per quarter as R&D intensity proxy"
    CATEGORY = "patents"
    ENTITY_TYPE = "company"
    FREQUENCY = "quarterly"
    LOOKBACK_DAYS = 365

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 365,
    ) -> Optional[float]:
        """Compute R&D intensity proxy.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_days: Lookback period

        Returns:
            Patents per quarter
        """
        ref_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_r_and_d_intensity_proxy(entity_id, ref_date, lookback_days)


@FactorRegistry.register
class InventorRetention(BaseFactor):
    """Inventor Retention Factor.

    Percentage of inventors with multiple patents.
    Higher retention indicates strong R&D culture.
    """

    FACTOR_NAME = "inventor_retention"
    FACTOR_DESCRIPTION = "Percentage of repeat inventors"
    CATEGORY = "patents"
    ENTITY_TYPE = "company"
    FREQUENCY = "annually"
    LOOKBACK_DAYS = 730

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 730,
    ) -> Optional[float]:
        """Compute inventor retention rate.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_days: Lookback period

        Returns:
            Retention percentage
        """
        ref_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_inventor_retention(entity_id, ref_date, lookback_days)

"""GitHub activity-derived factor computations."""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.github import (
    GitHubRepository,
    GitHubRepoMetrics,
    GitHubCommit,
    GitHubRelease,
    DeveloperActivity,
)
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_developer_velocity(
    ticker: str,
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate developer velocity (commits per day).

    Args:
        ticker: Stock ticker
        target_date: Reference date
        lookback_days: Days to analyze

    Returns:
        Average commits per day
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Get repos for ticker
        repos = (
            session.query(GitHubRepository.repo_id)
            .filter(GitHubRepository.ticker == ticker)
            .all()
        )

        if not repos:
            return None

        repo_ids = [r[0] for r in repos]

        # Count commits
        commit_count = (
            session.query(func.count(GitHubCommit.id))
            .filter(
                GitHubCommit.repo_id.in_(repo_ids),
                func.date(GitHubCommit.author_date) >= start_date,
                func.date(GitHubCommit.author_date) <= target_date,
            )
            .scalar()
        ) or 0

        return commit_count / lookback_days
    finally:
        session.close()


def calc_commit_momentum(
    ticker: str,
    target_date: date,
    short_window: int = 7,
    long_window: int = 30,
) -> Optional[float]:
    """Calculate commit momentum (short vs long term).

    Args:
        ticker: Stock ticker
        target_date: Reference date
        short_window: Short-term window in days
        long_window: Long-term window in days

    Returns:
        Momentum ratio (> 1 = increasing activity)
    """
    session = SessionLocal()
    try:
        short_start = target_date - timedelta(days=short_window)
        long_start = target_date - timedelta(days=long_window)

        repos = (
            session.query(GitHubRepository.repo_id)
            .filter(GitHubRepository.ticker == ticker)
            .all()
        )

        if not repos:
            return None

        repo_ids = [r[0] for r in repos]

        short_count = (
            session.query(func.count(GitHubCommit.id))
            .filter(
                GitHubCommit.repo_id.in_(repo_ids),
                func.date(GitHubCommit.author_date) >= short_start,
                func.date(GitHubCommit.author_date) <= target_date,
            )
            .scalar()
        ) or 0

        long_count = (
            session.query(func.count(GitHubCommit.id))
            .filter(
                GitHubCommit.repo_id.in_(repo_ids),
                func.date(GitHubCommit.author_date) >= long_start,
                func.date(GitHubCommit.author_date) <= target_date,
            )
            .scalar()
        ) or 0

        if long_count == 0:
            return None

        short_rate = short_count / short_window
        long_rate = long_count / long_window

        if long_rate == 0:
            return None

        return short_rate / long_rate
    finally:
        session.close()


def calc_release_frequency(
    ticker: str,
    target_date: date,
    lookback_days: int = 90,
) -> Optional[float]:
    """Calculate release frequency (releases per month).

    Args:
        ticker: Stock ticker
        target_date: Reference date
        lookback_days: Days to analyze

    Returns:
        Releases per 30 days
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        repos = (
            session.query(GitHubRepository.repo_id)
            .filter(GitHubRepository.ticker == ticker)
            .all()
        )

        if not repos:
            return None

        repo_ids = [r[0] for r in repos]

        release_count = (
            session.query(func.count(GitHubRelease.id))
            .filter(
                GitHubRelease.repo_id.in_(repo_ids),
                GitHubRelease.is_prerelease == False,
                func.date(GitHubRelease.published_at) >= start_date,
                func.date(GitHubRelease.published_at) <= target_date,
            )
            .scalar()
        ) or 0

        return (release_count / lookback_days) * 30
    finally:
        session.close()


def calc_star_growth_rate(
    repo_full_name: str,
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate star growth rate.

    Args:
        repo_full_name: Repository full name
        target_date: Reference date
        lookback_days: Days to analyze

    Returns:
        Daily star growth rate
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        current = (
            session.query(GitHubRepoMetrics.stars)
            .filter(
                GitHubRepoMetrics.full_name == repo_full_name,
                GitHubRepoMetrics.date == target_date,
            )
            .scalar()
        )

        previous = (
            session.query(GitHubRepoMetrics.stars)
            .filter(
                GitHubRepoMetrics.full_name == repo_full_name,
                GitHubRepoMetrics.date == start_date,
            )
            .scalar()
        )

        if current is None or previous is None or previous == 0:
            return None

        return (current - previous) / lookback_days
    finally:
        session.close()


def calc_contributor_diversity(
    ticker: str,
    target_date: date,
    lookback_days: int = 30,
) -> Optional[int]:
    """Calculate unique contributors.

    Args:
        ticker: Stock ticker
        target_date: Reference date
        lookback_days: Days to analyze

    Returns:
        Number of unique contributors
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        repos = (
            session.query(GitHubRepository.repo_id)
            .filter(GitHubRepository.ticker == ticker)
            .all()
        )

        if not repos:
            return None

        repo_ids = [r[0] for r in repos]

        unique_authors = (
            session.query(func.count(func.distinct(GitHubCommit.author_login)))
            .filter(
                GitHubCommit.repo_id.in_(repo_ids),
                func.date(GitHubCommit.author_date) >= start_date,
                func.date(GitHubCommit.author_date) <= target_date,
                GitHubCommit.author_login.isnot(None),
            )
            .scalar()
        )

        return int(unique_authors) if unique_authors else 0
    finally:
        session.close()


def calc_tech_sector_activity(
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate overall tech sector GitHub activity.

    Args:
        target_date: Reference date
        lookback_days: Days to analyze

    Returns:
        Tech sector activity index
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Sum commits across all tracked repos
        total_commits = (
            session.query(func.sum(GitHubRepoMetrics.commits_24h))
            .filter(
                GitHubRepoMetrics.date >= start_date,
                GitHubRepoMetrics.date <= target_date,
            )
            .scalar()
        ) or 0

        # Normalize to index (assume 1000 commits/week = index 100)
        return min(float(total_commits) / 1000 * 100, 200)
    finally:
        session.close()


@FactorRegistry.register
class DeveloperVelocity(BaseFactor):
    """Developer Velocity Factor.

    Measures development activity via commits per day.
    Higher = more active development.
    """

    FACTOR_NAME = "developer_velocity"
    FACTOR_DESCRIPTION = "Development velocity (commits/day)"
    CATEGORY = "github"
    ENTITY_TYPE = "ticker"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Ticker
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute developer velocity."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_developer_velocity(entity_id, target_date, lookback_days)


@FactorRegistry.register
class CommitMomentum(BaseFactor):
    """Commit Momentum Factor.

    Measures acceleration in development activity.
    > 1 = activity increasing, < 1 = decreasing.
    """

    FACTOR_NAME = "commit_momentum"
    FACTOR_DESCRIPTION = "Commit momentum (7d vs 30d rate)"
    CATEGORY = "github"
    ENTITY_TYPE = "ticker"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute commit momentum."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_commit_momentum(entity_id, target_date)


@FactorRegistry.register
class ReleaseFrequency(BaseFactor):
    """Release Frequency Factor.

    Measures product release cadence.
    Higher = faster product iteration.
    """

    FACTOR_NAME = "release_frequency"
    FACTOR_DESCRIPTION = "Release frequency (per month)"
    CATEGORY = "github"
    ENTITY_TYPE = "ticker"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 90

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 90,
    ) -> Optional[float]:
        """Compute release frequency."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_release_frequency(entity_id, target_date, lookback_days)


@FactorRegistry.register
class StarGrowthRate(BaseFactor):
    """Star Growth Rate Factor.

    Measures repository popularity growth.
    """

    FACTOR_NAME = "star_growth_rate"
    FACTOR_DESCRIPTION = "Daily star growth rate"
    CATEGORY = "github"
    ENTITY_TYPE = "repository"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Repository full name
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute star growth rate."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_star_growth_rate(entity_id, target_date, lookback_days)


@FactorRegistry.register
class ContributorDiversity(BaseFactor):
    """Contributor Diversity Factor.

    Measures breadth of development team.
    Higher = more diverse contributor base.
    """

    FACTOR_NAME = "contributor_diversity"
    FACTOR_DESCRIPTION = "Unique contributors count"
    CATEGORY = "github"
    ENTITY_TYPE = "ticker"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 30,
    ) -> Optional[float]:
        """Compute contributor diversity."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        result = calc_contributor_diversity(entity_id, target_date, lookback_days)
        return float(result) if result is not None else None


@FactorRegistry.register
class TechSectorActivity(BaseFactor):
    """Tech Sector Activity Factor.

    Overall GitHub activity across tech companies.
    Proxy for sector development momentum.
    """

    FACTOR_NAME = "tech_sector_activity"
    FACTOR_DESCRIPTION = "Tech sector GitHub activity index"
    CATEGORY = "github"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Ignored
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute tech sector activity."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_tech_sector_activity(target_date, lookback_days)

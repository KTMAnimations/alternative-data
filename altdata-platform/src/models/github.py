"""Database models for GitHub activity data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Index, JSON, Text, Date, Boolean
)

from src.models.database import Base


class GitHubRepository(Base):
    """Tracked GitHub repositories."""
    __tablename__ = "github_repositories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    repo_id = Column(BigInteger, nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=False, unique=True, index=True)  # owner/repo
    name = Column(String(255), index=True)
    owner = Column(String(100), index=True)
    description = Column(Text)

    # Repo metadata
    language = Column(String(50), index=True)
    topics = Column(JSON)  # List of topics
    is_fork = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    pushed_at = Column(DateTime(timezone=True))

    # Associated company/ticker
    company = Column(String(255))
    ticker = Column(String(10), index=True)

    # Tracking info
    is_tracked = Column(Boolean, default=True)
    added_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_github_repo_owner", "owner"),
        Index("ix_github_repo_ticker", "ticker"),
    )


class GitHubRepoMetrics(Base):
    """Daily repository metrics snapshots."""
    __tablename__ = "github_repo_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    repo_id = Column(BigInteger, nullable=False, index=True)
    full_name = Column(String(255), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # Popularity metrics
    stars = Column(Integer)
    forks = Column(Integer)
    watchers = Column(Integer)
    open_issues = Column(Integer)

    # Activity metrics (from API events)
    commits_24h = Column(Integer)
    prs_opened_24h = Column(Integer)
    prs_merged_24h = Column(Integer)
    issues_opened_24h = Column(Integer)
    issues_closed_24h = Column(Integer)

    # Contributors
    contributors_active_24h = Column(Integer)
    unique_committers_24h = Column(Integer)

    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_github_metrics_repo_date", "repo_id", "date"),
        Index("ix_github_metrics_name_date", "full_name", "date"),
    )


class GitHubCommit(Base):
    """Individual commit records."""
    __tablename__ = "github_commits"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sha = Column(String(40), nullable=False, unique=True, index=True)
    repo_id = Column(BigInteger, nullable=False, index=True)
    full_name = Column(String(255), index=True)

    author_login = Column(String(100), index=True)
    author_email = Column(String(255))
    author_date = Column(DateTime(timezone=True), nullable=False, index=True)
    committer_login = Column(String(100))
    committer_date = Column(DateTime(timezone=True))

    message = Column(Text)
    additions = Column(Integer)
    deletions = Column(Integer)
    files_changed = Column(Integer)

    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_github_commit_repo_date", "repo_id", "author_date"),
    )


class GitHubRelease(Base):
    """Software releases."""
    __tablename__ = "github_releases"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    release_id = Column(BigInteger, nullable=False, unique=True, index=True)
    repo_id = Column(BigInteger, nullable=False, index=True)
    full_name = Column(String(255), index=True)

    tag_name = Column(String(100))
    name = Column(String(255))
    body = Column(Text)
    is_prerelease = Column(Boolean, default=False)
    is_draft = Column(Boolean, default=False)

    author_login = Column(String(100))
    published_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True))

    # Download stats
    download_count = Column(Integer)

    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_github_release_repo_pub", "repo_id", "published_at"),
    )


class GitHubPullRequest(Base):
    """Pull request activity."""
    __tablename__ = "github_pull_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pr_id = Column(BigInteger, nullable=False, unique=True, index=True)
    pr_number = Column(Integer, nullable=False)
    repo_id = Column(BigInteger, nullable=False, index=True)
    full_name = Column(String(255), index=True)

    title = Column(Text)
    state = Column(String(20), index=True)  # open, closed, merged
    author_login = Column(String(100), index=True)

    created_at = Column(DateTime(timezone=True), index=True)
    updated_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    merged_at = Column(DateTime(timezone=True))

    additions = Column(Integer)
    deletions = Column(Integer)
    changed_files = Column(Integer)
    comments = Column(Integer)
    review_comments = Column(Integer)

    labels = Column(JSON)

    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_github_pr_repo_created", "repo_id", "created_at"),
        Index("ix_github_pr_state", "state"),
    )


class DeveloperActivity(Base):
    """Daily aggregated developer activity by company."""
    __tablename__ = "developer_activity"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company = Column(String(255), nullable=False, index=True)
    ticker = Column(String(10), index=True)
    date = Column(Date, nullable=False, index=True)

    # Aggregated metrics
    total_commits = Column(Integer)
    total_prs = Column(Integer)
    total_releases = Column(Integer)
    active_repos = Column(Integer)
    unique_contributors = Column(Integer)

    # Change metrics
    commits_change_7d = Column(Float)  # % change vs 7d ago
    commits_change_30d = Column(Float)  # % change vs 30d ago

    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dev_activity_company_date", "company", "date"),
        Index("ix_dev_activity_ticker_date", "ticker", "date"),
    )

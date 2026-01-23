"""Tests for GitHub activity data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from src.collectors.github_activity import GitHubActivityCollector
from src.models.github import (
    GitHubRepository,
    GitHubRepoMetrics,
    GitHubCommit,
    GitHubRelease,
    GitHubPullRequest,
    DeveloperActivity,
)
from src.transformations.factors.github_factors import (
    calc_developer_velocity,
    calc_commit_momentum,
    calc_release_frequency,
    calc_star_growth_rate,
    calc_contributor_diversity,
    calc_tech_sector_activity,
    DeveloperVelocity,
    CommitMomentum,
    ReleaseFrequency,
    StarGrowthRate,
    ContributorDiversity,
    TechSectorActivity,
)


# =============================================================================
# GitHub Model Tests
# =============================================================================

class TestGitHubModels:
    """Test GitHub database models."""

    def test_github_repository_model(self):
        """Test GitHubRepository model creation."""
        repo = GitHubRepository(
            repo_id=12345678,
            full_name="microsoft/vscode",
            name="vscode",
            owner="microsoft",
            description="Visual Studio Code",
            language="TypeScript",
            topics=["editor", "typescript", "electron"],
            company="Microsoft",
            ticker="MSFT",
        )
        assert repo.full_name == "microsoft/vscode"
        assert repo.ticker == "MSFT"
        assert "editor" in repo.topics

    def test_github_repo_metrics_model(self):
        """Test GitHubRepoMetrics model creation."""
        metrics = GitHubRepoMetrics(
            repo_id=12345678,
            full_name="microsoft/vscode",
            date=date.today(),
            stars=150000,
            forks=25000,
            watchers=5000,
            open_issues=8000,
            commits_24h=150,
            prs_opened_24h=45,
            prs_merged_24h=30,
            unique_committers_24h=25,
        )
        assert metrics.stars == 150000
        assert metrics.commits_24h == 150

    def test_github_commit_model(self):
        """Test GitHubCommit model creation."""
        commit = GitHubCommit(
            sha="abc123def456789",
            repo_id=12345678,
            full_name="facebook/react",
            author_login="developer123",
            author_email="dev@example.com",
            author_date=datetime.utcnow(),
            message="Fix critical bug",
            additions=100,
            deletions=50,
        )
        assert commit.sha == "abc123def456789"
        assert commit.author_login == "developer123"

    def test_github_release_model(self):
        """Test GitHubRelease model creation."""
        release = GitHubRelease(
            release_id=987654,
            repo_id=12345678,
            full_name="hashicorp/terraform",
            tag_name="v1.5.0",
            name="Terraform 1.5.0",
            is_prerelease=False,
            published_at=datetime.utcnow(),
        )
        assert release.tag_name == "v1.5.0"
        assert release.is_prerelease is False

    def test_github_pull_request_model(self):
        """Test GitHubPullRequest model creation."""
        pr = GitHubPullRequest(
            pr_id=123456,
            pr_number=42,
            repo_id=12345678,
            full_name="google/guava",
            title="Add new utility method",
            state="merged",
            author_login="contributor",
            created_at=datetime.utcnow(),
            merged_at=datetime.utcnow(),
            labels=["enhancement", "approved"],
        )
        assert pr.state == "merged"
        assert "enhancement" in pr.labels

    def test_developer_activity_model(self):
        """Test DeveloperActivity model creation."""
        activity = DeveloperActivity(
            company="Google",
            ticker="GOOGL",
            date=date.today(),
            total_commits=500,
            total_prs=100,
            total_releases=5,
            active_repos=15,
            unique_contributors=75,
            commits_change_7d=15.5,
        )
        assert activity.total_commits == 500
        assert activity.commits_change_7d == 15.5


# =============================================================================
# GitHub Activity Collector Tests
# =============================================================================

class TestGitHubActivityCollector:
    """Test GitHub activity collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = GitHubActivityCollector(token="test_token")
        assert collector.token == "test_token"
        assert collector.SOURCE_NAME == "github_activity"

    def test_tracked_repos(self):
        """Test tracked repos configuration."""
        collector = GitHubActivityCollector()
        assert len(collector.TRACKED_REPOS) >= 10

        # Check for major tech companies
        full_names = [r["full_name"] for r in collector.TRACKED_REPOS]
        assert "microsoft/vscode" in full_names
        assert "facebook/react" in full_names

        # Check ticker mapping
        msft_repos = [r for r in collector.TRACKED_REPOS if r.get("ticker") == "MSFT"]
        assert len(msft_repos) >= 2

    def test_get_headers_with_token(self):
        """Test headers include auth token."""
        collector = GitHubActivityCollector(token="test_token")
        headers = collector._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "token test_token"

    def test_get_headers_without_token(self):
        """Test headers without auth token."""
        collector = GitHubActivityCollector(token=None)
        collector.token = None
        headers = collector._get_headers()
        assert "Authorization" not in headers
        assert "Accept" in headers

    def test_parse_repository(self):
        """Test repository parsing."""
        collector = GitHubActivityCollector()
        raw_repo = {
            "id": 12345,
            "full_name": "owner/repo",
            "name": "repo",
            "owner": {"login": "owner"},
            "description": "Test repo",
            "language": "Python",
            "topics": ["python", "api"],
            "fork": False,
            "created_at": "2024-01-01T00:00:00Z",
        }
        meta = {"company": "TestCo", "ticker": "TEST"}

        parsed = collector.parse_repository(raw_repo, meta)

        assert parsed["repo_id"] == 12345
        assert parsed["full_name"] == "owner/repo"
        assert parsed["company"] == "TestCo"
        assert parsed["ticker"] == "TEST"

    def test_parse_commit(self):
        """Test commit parsing."""
        collector = GitHubActivityCollector()
        raw_commit = {
            "sha": "abc123",
            "commit": {
                "author": {
                    "email": "dev@example.com",
                    "date": "2024-06-15T10:00:00Z",
                },
                "committer": {"date": "2024-06-15T10:00:00Z"},
                "message": "Fix bug",
            },
            "author": {"login": "developer"},
            "committer": {"login": "developer"},
        }

        parsed = collector.parse_commit(raw_commit, 12345, "owner/repo")

        assert parsed["sha"] == "abc123"
        assert parsed["author_login"] == "developer"
        assert parsed["author_date"] is not None

    def test_parse_pull_request(self):
        """Test PR parsing."""
        collector = GitHubActivityCollector()
        raw_pr = {
            "id": 98765,
            "number": 42,
            "title": "New feature",
            "state": "open",
            "user": {"login": "contributor"},
            "created_at": "2024-06-15T10:00:00Z",
            "labels": [{"name": "enhancement"}],
        }

        parsed = collector.parse_pull_request(raw_pr, 12345, "owner/repo")

        assert parsed["pr_id"] == 98765
        assert parsed["pr_number"] == 42
        assert parsed["state"] == "open"
        assert "enhancement" in parsed["labels"]

    def test_parse_release(self):
        """Test release parsing."""
        collector = GitHubActivityCollector()
        raw_release = {
            "id": 11111,
            "tag_name": "v2.0.0",
            "name": "Version 2.0",
            "body": "Major release",
            "prerelease": False,
            "draft": False,
            "author": {"login": "maintainer"},
            "published_at": "2024-06-15T10:00:00Z",
        }

        parsed = collector.parse_release(raw_release, 12345, "owner/repo")

        assert parsed["release_id"] == 11111
        assert parsed["tag_name"] == "v2.0.0"
        assert parsed["is_prerelease"] is False

    def test_parse_datetime(self):
        """Test datetime parsing."""
        collector = GitHubActivityCollector()

        dt = collector._parse_datetime("2024-06-15T10:30:00Z")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 6
        assert dt.day == 15

    def test_parse_datetime_none(self):
        """Test datetime parsing with None."""
        collector = GitHubActivityCollector()

        dt = collector._parse_datetime(None)
        assert dt is None

    def test_parse_returns_structured_data(self):
        """Test parse returns proper structure."""
        collector = GitHubActivityCollector()
        raw_data = [
            {
                "_meta": {"full_name": "owner/repo", "company": "Test", "ticker": "TST"},
                "repo": {"id": 12345, "full_name": "owner/repo", "stargazers_count": 100},
                "commits": [{"sha": "abc", "commit": {"author": {"date": "2024-06-15T10:00:00Z"}}}],
                "pull_requests": [],
                "releases": [],
            }
        ]

        parsed = collector.parse(raw_data)

        assert "repositories" in parsed
        assert "metrics" in parsed
        assert "commits" in parsed


# =============================================================================
# GitHub Factor Calculation Tests
# =============================================================================

class TestGitHubFactorCalculations:
    """Test GitHub factor calculation functions."""

    @patch("src.transformations.factors.github_factors.SessionLocal")
    def test_calc_developer_velocity(self, mock_session_local):
        """Test developer velocity calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Mock repos query
        mock_session.query.return_value.filter.return_value.all.return_value = [(12345,)]
        # Mock commit count: 70 commits in 7 days
        mock_session.query.return_value.filter.return_value.scalar.return_value = 70

        result = calc_developer_velocity("MSFT", date(2024, 6, 15), lookback_days=7)

        # 70 commits / 7 days = 10 commits/day
        assert result == 10.0
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.github_factors.SessionLocal")
    def test_calc_commit_momentum(self, mock_session_local):
        """Test commit momentum calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.all.return_value = [(12345,)]
        # Short: 35 commits in 7 days, Long: 90 commits in 30 days
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [35, 90]

        result = calc_commit_momentum("GOOGL", date(2024, 6, 15))

        # short_rate = 35/7 = 5, long_rate = 90/30 = 3
        # momentum = 5/3 = 1.67
        assert result is not None
        assert abs(result - 1.67) < 0.1

    @patch("src.transformations.factors.github_factors.SessionLocal")
    def test_calc_release_frequency(self, mock_session_local):
        """Test release frequency calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.all.return_value = [(12345,)]
        # 6 releases in 90 days
        mock_session.query.return_value.filter.return_value.scalar.return_value = 6

        result = calc_release_frequency("META", date(2024, 6, 15), lookback_days=90)

        # (6/90) * 30 = 2 releases per month
        assert result == 2.0

    @patch("src.transformations.factors.github_factors.SessionLocal")
    def test_calc_star_growth_rate(self, mock_session_local):
        """Test star growth rate calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Current: 1070 stars, Previous (7 days ago): 1000 stars
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [1070, 1000]

        result = calc_star_growth_rate("owner/repo", date(2024, 6, 15))

        # (1070 - 1000) / 7 = 10 stars/day
        assert result == 10.0

    @patch("src.transformations.factors.github_factors.SessionLocal")
    def test_calc_contributor_diversity(self, mock_session_local):
        """Test contributor diversity calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.all.return_value = [(12345,)]
        mock_session.query.return_value.filter.return_value.scalar.return_value = 45

        result = calc_contributor_diversity("NVDA", date(2024, 6, 15))

        assert result == 45

    @patch("src.transformations.factors.github_factors.SessionLocal")
    def test_calc_tech_sector_activity(self, mock_session_local):
        """Test tech sector activity calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # 800 total commits in period
        mock_session.query.return_value.filter.return_value.scalar.return_value = 800

        result = calc_tech_sector_activity(date(2024, 6, 15))

        # (800/1000) * 100 = 80
        assert result == 80.0


# =============================================================================
# GitHub Factor Class Tests
# =============================================================================

class TestGitHubFactorClasses:
    """Test GitHub factor classes."""

    def test_developer_velocity_factor(self):
        """Test DeveloperVelocity factor class."""
        factor = DeveloperVelocity()
        assert factor.FACTOR_NAME == "developer_velocity"
        assert factor.CATEGORY == "github"
        assert factor.ENTITY_TYPE == "ticker"

    def test_commit_momentum_factor(self):
        """Test CommitMomentum factor class."""
        factor = CommitMomentum()
        assert factor.FACTOR_NAME == "commit_momentum"
        assert factor.LOOKBACK_DAYS == 30

    def test_release_frequency_factor(self):
        """Test ReleaseFrequency factor class."""
        factor = ReleaseFrequency()
        assert factor.FACTOR_NAME == "release_frequency"
        assert factor.LOOKBACK_DAYS == 90

    def test_star_growth_rate_factor(self):
        """Test StarGrowthRate factor class."""
        factor = StarGrowthRate()
        assert factor.FACTOR_NAME == "star_growth_rate"
        assert factor.ENTITY_TYPE == "repository"

    def test_contributor_diversity_factor(self):
        """Test ContributorDiversity factor class."""
        factor = ContributorDiversity()
        assert factor.FACTOR_NAME == "contributor_diversity"
        assert "contributor" in factor.FACTOR_DESCRIPTION.lower()

    def test_tech_sector_activity_factor(self):
        """Test TechSectorActivity factor class."""
        factor = TechSectorActivity()
        assert factor.FACTOR_NAME == "tech_sector_activity"
        assert factor.ENTITY_TYPE == "market"

    @patch("src.transformations.factors.github_factors.calc_developer_velocity")
    def test_developer_velocity_compute(self, mock_calc):
        """Test DeveloperVelocity compute method."""
        mock_calc.return_value = 15.5

        factor = DeveloperVelocity()
        result = factor.compute("MSFT", datetime(2024, 6, 15))

        assert result == 15.5
        mock_calc.assert_called_once()

    @patch("src.transformations.factors.github_factors.calc_tech_sector_activity")
    def test_tech_sector_activity_compute(self, mock_calc):
        """Test TechSectorActivity compute method."""
        mock_calc.return_value = 95.0

        factor = TechSectorActivity()
        result = factor.compute("market", datetime(2024, 6, 15))

        assert result == 95.0


# =============================================================================
# Factor Registry Tests
# =============================================================================

class TestGitHubFactorRegistry:
    """Test GitHub factors in registry."""

    def test_github_factors_registered(self):
        """Test that all GitHub factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        github_factors = [
            "developer_velocity",
            "commit_momentum",
            "release_frequency",
            "star_growth_rate",
            "contributor_diversity",
            "tech_sector_activity",
        ]

        for factor in github_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_github_factors_category(self):
        """Test GitHub factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        github_factors = [f for f in registered if f["category"] == "github"]

        assert len(github_factors) >= 6

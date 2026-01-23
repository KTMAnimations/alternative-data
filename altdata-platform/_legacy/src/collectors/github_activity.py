"""GitHub activity collector for developer signals."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.github import (
    GitHubRepository,
    GitHubRepoMetrics,
    GitHubCommit,
    GitHubRelease,
    GitHubPullRequest,
)

logger = logging.getLogger(__name__)


class GitHubActivityCollector(BaseCollector[Dict, Dict]):
    """Collector for GitHub activity data.

    Tracks developer activity as signals for tech companies.
    """

    SOURCE_NAME = "github_activity"
    BASE_URL = "https://api.github.com"
    DEFAULT_RATE_LIMIT = 1.0  # 5000 requests/hour with auth

    # Major tech company repos to track
    TRACKED_REPOS = [
        # FAANG
        {"full_name": "facebook/react", "company": "Meta", "ticker": "META"},
        {"full_name": "facebook/react-native", "company": "Meta", "ticker": "META"},
        {"full_name": "pytorch/pytorch", "company": "Meta", "ticker": "META"},
        {"full_name": "apple/swift", "company": "Apple", "ticker": "AAPL"},
        {"full_name": "apple/swift-nio", "company": "Apple", "ticker": "AAPL"},
        {"full_name": "amzn/style-dictionary", "company": "Amazon", "ticker": "AMZN"},
        {"full_name": "aws/aws-cdk", "company": "Amazon", "ticker": "AMZN"},
        {"full_name": "netflix/conductor", "company": "Netflix", "ticker": "NFLX"},
        {"full_name": "google/guava", "company": "Google", "ticker": "GOOGL"},
        {"full_name": "google/jax", "company": "Google", "ticker": "GOOGL"},
        {"full_name": "tensorflow/tensorflow", "company": "Google", "ticker": "GOOGL"},

        # Microsoft
        {"full_name": "microsoft/vscode", "company": "Microsoft", "ticker": "MSFT"},
        {"full_name": "microsoft/TypeScript", "company": "Microsoft", "ticker": "MSFT"},
        {"full_name": "dotnet/runtime", "company": "Microsoft", "ticker": "MSFT"},
        {"full_name": "Azure/azure-sdk-for-python", "company": "Microsoft", "ticker": "MSFT"},

        # NVIDIA
        {"full_name": "NVIDIA/cuda-samples", "company": "NVIDIA", "ticker": "NVDA"},
        {"full_name": "NVIDIA/TensorRT", "company": "NVIDIA", "ticker": "NVDA"},

        # Other tech
        {"full_name": "openai/openai-python", "company": "OpenAI", "ticker": None},
        {"full_name": "anthropics/anthropic-sdk-python", "company": "Anthropic", "ticker": None},
        {"full_name": "vercel/next.js", "company": "Vercel", "ticker": None},
        {"full_name": "docker/compose", "company": "Docker", "ticker": None},

        # Enterprise
        {"full_name": "hashicorp/terraform", "company": "HashiCorp", "ticker": "HCP"},
        {"full_name": "elastic/elasticsearch", "company": "Elastic", "ticker": "ESTC"},
        {"full_name": "mongodb/mongo", "company": "MongoDB", "ticker": "MDB"},
        {"full_name": "cockroachdb/cockroach", "company": "Cockroach Labs", "ticker": None},
        {"full_name": "snowflakedb/snowflake-connector-python", "company": "Snowflake", "ticker": "SNOW"},
    ]

    def __init__(
        self,
        token: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the GitHub activity collector.

        Args:
            token: GitHub personal access token
            rate_limit: Requests per second
        """
        super().__init__(rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT)
        self.token = token or getattr(settings, 'github_token', None)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AltData-Platform/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    async def fetch(self) -> List[Dict]:
        """Fetch activity for all tracked repos.

        Returns:
            List of repo activity data
        """
        results = []
        for repo_info in self.TRACKED_REPOS:
            try:
                await self.rate_limiter.wait()
                data = await self.fetch_repo_data(repo_info["full_name"])
                if data:
                    data["_meta"] = repo_info
                    results.append(data)
            except Exception as e:
                logger.warning(f"Failed to fetch {repo_info['full_name']}: {e}")
        return results

    async def fetch_repo_data(self, full_name: str) -> Optional[Dict]:
        """Fetch repository data and metrics.

        Args:
            full_name: Repository full name (owner/repo)

        Returns:
            Repository data dict or None
        """
        try:
            # Get repo info
            response = await self.http_client.get(
                f"{self.BASE_URL}/repos/{full_name}",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            repo_data = response.json()

            # Get recent commits
            await self.rate_limiter.wait()
            commits_response = await self.http_client.get(
                f"{self.BASE_URL}/repos/{full_name}/commits",
                headers=self._get_headers(),
                params={"per_page": 100},
            )
            commits = commits_response.json() if commits_response.status_code == 200 else []

            # Get recent PRs
            await self.rate_limiter.wait()
            prs_response = await self.http_client.get(
                f"{self.BASE_URL}/repos/{full_name}/pulls",
                headers=self._get_headers(),
                params={"state": "all", "per_page": 100},
            )
            prs = prs_response.json() if prs_response.status_code == 200 else []

            # Get releases
            await self.rate_limiter.wait()
            releases_response = await self.http_client.get(
                f"{self.BASE_URL}/repos/{full_name}/releases",
                headers=self._get_headers(),
                params={"per_page": 10},
            )
            releases = releases_response.json() if releases_response.status_code == 200 else []

            return {
                "repo": repo_data,
                "commits": commits,
                "pull_requests": prs,
                "releases": releases,
            }

        except Exception as e:
            logger.error(f"Error fetching {full_name}: {e}")
            return None

    def parse(self, raw_data: List[Dict]) -> Dict:
        """Parse raw API responses.

        Args:
            raw_data: List of repo data dicts

        Returns:
            Parsed data structure
        """
        repositories = []
        metrics = []
        commits = []
        pull_requests = []
        releases = []

        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)

        for data in raw_data:
            meta = data.get("_meta", {})
            repo = data.get("repo", {})

            # Parse repository
            parsed_repo = self.parse_repository(repo, meta)
            if parsed_repo:
                repositories.append(parsed_repo)

            # Parse commits and calculate 24h metrics
            commits_24h = 0
            unique_authors = set()
            for commit in data.get("commits", []):
                parsed_commit = self.parse_commit(commit, repo.get("id"), meta.get("full_name"))
                if parsed_commit:
                    commits.append(parsed_commit)
                    if parsed_commit["author_date"].date() >= yesterday:
                        commits_24h += 1
                        if parsed_commit.get("author_login"):
                            unique_authors.add(parsed_commit["author_login"])

            # Parse PRs
            prs_opened_24h = 0
            prs_merged_24h = 0
            for pr in data.get("pull_requests", []):
                parsed_pr = self.parse_pull_request(pr, repo.get("id"), meta.get("full_name"))
                if parsed_pr:
                    pull_requests.append(parsed_pr)
                    if parsed_pr["created_at"] and parsed_pr["created_at"].date() >= yesterday:
                        prs_opened_24h += 1
                    if parsed_pr.get("merged_at") and parsed_pr["merged_at"].date() >= yesterday:
                        prs_merged_24h += 1

            # Parse releases
            for release in data.get("releases", []):
                parsed_release = self.parse_release(release, repo.get("id"), meta.get("full_name"))
                if parsed_release:
                    releases.append(parsed_release)

            # Create daily metrics
            metrics.append({
                "repo_id": repo.get("id"),
                "full_name": meta.get("full_name"),
                "date": today,
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),
                "watchers": repo.get("watchers_count"),
                "open_issues": repo.get("open_issues_count"),
                "commits_24h": commits_24h,
                "prs_opened_24h": prs_opened_24h,
                "prs_merged_24h": prs_merged_24h,
                "unique_committers_24h": len(unique_authors),
            })

        return {
            "repositories": repositories,
            "metrics": metrics,
            "commits": commits,
            "pull_requests": pull_requests,
            "releases": releases,
        }

    def parse_repository(self, repo: Dict, meta: Dict) -> Optional[Dict]:
        """Parse repository data.

        Args:
            repo: Raw repo data
            meta: Metadata dict

        Returns:
            Parsed repo dict or None
        """
        if not repo.get("id"):
            return None

        return {
            "repo_id": repo["id"],
            "full_name": repo.get("full_name"),
            "name": repo.get("name"),
            "owner": repo.get("owner", {}).get("login"),
            "description": repo.get("description"),
            "language": repo.get("language"),
            "topics": repo.get("topics", []),
            "is_fork": repo.get("fork", False),
            "created_at": self._parse_datetime(repo.get("created_at")),
            "updated_at": self._parse_datetime(repo.get("updated_at")),
            "pushed_at": self._parse_datetime(repo.get("pushed_at")),
            "company": meta.get("company"),
            "ticker": meta.get("ticker"),
        }

    def parse_commit(self, commit: Dict, repo_id: int, full_name: str) -> Optional[Dict]:
        """Parse commit data.

        Args:
            commit: Raw commit data
            repo_id: Repository ID
            full_name: Repository full name

        Returns:
            Parsed commit dict or None
        """
        sha = commit.get("sha")
        if not sha:
            return None

        commit_data = commit.get("commit", {})
        author = commit_data.get("author", {})

        return {
            "sha": sha,
            "repo_id": repo_id,
            "full_name": full_name,
            "author_login": commit.get("author", {}).get("login") if commit.get("author") else None,
            "author_email": author.get("email"),
            "author_date": self._parse_datetime(author.get("date")),
            "committer_login": commit.get("committer", {}).get("login") if commit.get("committer") else None,
            "committer_date": self._parse_datetime(commit_data.get("committer", {}).get("date")),
            "message": commit_data.get("message", "")[:1000],
        }

    def parse_pull_request(self, pr: Dict, repo_id: int, full_name: str) -> Optional[Dict]:
        """Parse pull request data.

        Args:
            pr: Raw PR data
            repo_id: Repository ID
            full_name: Repository full name

        Returns:
            Parsed PR dict or None
        """
        pr_id = pr.get("id")
        if not pr_id:
            return None

        return {
            "pr_id": pr_id,
            "pr_number": pr.get("number"),
            "repo_id": repo_id,
            "full_name": full_name,
            "title": pr.get("title", "")[:500],
            "state": pr.get("state"),
            "author_login": pr.get("user", {}).get("login") if pr.get("user") else None,
            "created_at": self._parse_datetime(pr.get("created_at")),
            "updated_at": self._parse_datetime(pr.get("updated_at")),
            "closed_at": self._parse_datetime(pr.get("closed_at")),
            "merged_at": self._parse_datetime(pr.get("merged_at")),
            "labels": [l.get("name") for l in pr.get("labels", [])],
        }

    def parse_release(self, release: Dict, repo_id: int, full_name: str) -> Optional[Dict]:
        """Parse release data.

        Args:
            release: Raw release data
            repo_id: Repository ID
            full_name: Repository full name

        Returns:
            Parsed release dict or None
        """
        release_id = release.get("id")
        if not release_id:
            return None

        return {
            "release_id": release_id,
            "repo_id": repo_id,
            "full_name": full_name,
            "tag_name": release.get("tag_name"),
            "name": release.get("name"),
            "body": release.get("body", "")[:5000] if release.get("body") else None,
            "is_prerelease": release.get("prerelease", False),
            "is_draft": release.get("draft", False),
            "author_login": release.get("author", {}).get("login") if release.get("author") else None,
            "published_at": self._parse_datetime(release.get("published_at")),
            "created_at": self._parse_datetime(release.get("created_at")),
        }

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string.

        Args:
            dt_str: ISO datetime string

        Returns:
            Parsed datetime or None
        """
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    async def store_data(self, parsed: Dict) -> Tuple[int, int, int]:
        """Store parsed GitHub data.

        Args:
            parsed: Parsed data dict

        Returns:
            Tuple of (repos_stored, metrics_stored, commits_stored)
        """
        session = SessionLocal()
        repos_count = 0
        metrics_count = 0
        commits_count = 0

        try:
            # Store repositories
            for repo in parsed.get("repositories", []):
                existing = session.query(GitHubRepository).filter_by(repo_id=repo["repo_id"]).first()
                if existing:
                    for key, value in repo.items():
                        if value is not None:
                            setattr(existing, key, value)
                else:
                    session.add(GitHubRepository(**repo))
                    repos_count += 1

            # Store metrics
            for metric in parsed.get("metrics", []):
                session.add(GitHubRepoMetrics(**metric))
                metrics_count += 1

            # Store commits (deduplicate by sha)
            for commit in parsed.get("commits", []):
                existing = session.query(GitHubCommit).filter_by(sha=commit["sha"]).first()
                if not existing:
                    session.add(GitHubCommit(**commit))
                    commits_count += 1

            session.commit()
            logger.info(
                f"Stored {repos_count} repos, {metrics_count} metrics, "
                f"{commits_count} commits"
            )

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store GitHub data: {e}")
            raise
        finally:
            session.close()

        return repos_count, metrics_count, commits_count

    async def run_collection(self) -> int:
        """Run full collection cycle.

        Returns:
            Total records stored
        """
        logger.info("Starting GitHub activity collection")

        try:
            raw_data = await self.fetch()
            if raw_data:
                await self.store_raw(raw_data)

            parsed = self.parse(raw_data)
            r, m, c = await self.store_data(parsed)

            total = r + m + c
            logger.info(f"GitHub activity collection complete: {total} records")
            return total

        finally:
            await self.close()

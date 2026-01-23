"""USPTO Patent data collector."""

import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
import re

import httpx

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.patents import Patent, PatentAssignee, PatentApplication

logger = logging.getLogger(__name__)


class USPTOCollector(BaseCollector[Dict, Dict]):
    """Collector for USPTO patent data.

    Uses USPTO Open Data Portal and PatentsView API.
    """

    SOURCE_NAME = "uspto"
    PATENTSVIEW_URL = "https://api.patentsview.org/patents/query"
    USPTO_BULK_URL = "https://bulkdata.uspto.gov"
    DEFAULT_RATE_LIMIT = 5.0  # PatentsView allows higher rates

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the USPTO collector.

        Args:
            api_key: Optional USPTO API key
            rate_limit: Requests per second
        """
        super().__init__(rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT)
        self.api_key = api_key or getattr(settings, 'uspto_api_key', None)

    async def fetch(self) -> Dict:
        """Fetch recent patent grants.

        Returns:
            Dict with patent data
        """
        # Default: fetch patents from last 7 days
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        return await self.fetch_patents_by_date(start_date, end_date)

    async def fetch_patents_by_date(
        self,
        start_date: date,
        end_date: date,
        page: int = 1,
        per_page: int = 100,
    ) -> Dict:
        """Fetch patents granted within date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            page: Page number
            per_page: Results per page

        Returns:
            Patent data dict
        """
        await self.rate_limiter.wait()

        query = {
            "q": {
                "_and": [
                    {"_gte": {"patent_date": start_date.isoformat()}},
                    {"_lte": {"patent_date": end_date.isoformat()}},
                ]
            },
            "f": [
                "patent_number",
                "patent_title",
                "patent_abstract",
                "patent_date",
                "patent_type",
                "patent_num_claims",
                "app_date",
                "assignee_organization",
                "assignee_city",
                "assignee_state",
                "assignee_country",
                "inventor_first_name",
                "inventor_last_name",
                "cpc_section_id",
                "cpc_subsection_id",
            ],
            "o": {
                "page": page,
                "per_page": per_page,
            },
        }

        try:
            response = await self.http_client.post(
                self.PATENTSVIEW_URL,
                json=query,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"USPTO fetch error: {e}")
            raise CollectorError(f"Failed to fetch USPTO data: {e}")

    async def fetch_patents_by_assignee(
        self,
        assignee_name: str,
        page: int = 1,
        per_page: int = 100,
    ) -> Dict:
        """Fetch patents by assignee (company) name.

        Args:
            assignee_name: Company name to search
            page: Page number
            per_page: Results per page

        Returns:
            Patent data dict
        """
        await self.rate_limiter.wait()

        query = {
            "q": {"_contains": {"assignee_organization": assignee_name}},
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_type",
                "patent_num_claims",
                "app_date",
                "assignee_organization",
                "cpc_section_id",
            ],
            "o": {
                "page": page,
                "per_page": per_page,
            },
            "s": [{"patent_date": "desc"}],
        }

        try:
            response = await self.http_client.post(
                self.PATENTSVIEW_URL,
                json=query,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"USPTO assignee fetch error: {e}")
            raise CollectorError(f"Failed to fetch USPTO data: {e}")

    async def fetch_patents_by_class(
        self,
        cpc_class: str,
        start_date: Optional[date] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> Dict:
        """Fetch patents by CPC classification.

        Args:
            cpc_class: CPC class code (e.g., "H04L" for networking)
            start_date: Optional start date filter
            page: Page number
            per_page: Results per page

        Returns:
            Patent data dict
        """
        await self.rate_limiter.wait()

        conditions = [{"_begins": {"cpc_subsection_id": cpc_class}}]
        if start_date:
            conditions.append({"_gte": {"patent_date": start_date.isoformat()}})

        query = {
            "q": {"_and": conditions} if len(conditions) > 1 else conditions[0],
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_type",
                "assignee_organization",
                "cpc_section_id",
                "cpc_subsection_id",
            ],
            "o": {
                "page": page,
                "per_page": per_page,
            },
            "s": [{"patent_date": "desc"}],
        }

        try:
            response = await self.http_client.post(
                self.PATENTSVIEW_URL,
                json=query,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"USPTO class fetch error: {e}")
            raise CollectorError(f"Failed to fetch USPTO data: {e}")

    def parse(self, raw_data: Dict) -> List[Dict]:
        """Parse USPTO API response into structured format.

        Args:
            raw_data: Raw API response

        Returns:
            List of parsed patent dicts
        """
        patents = raw_data.get("patents", [])
        parsed = []

        for patent in patents:
            try:
                # Extract assignees
                assignees = patent.get("assignees", [])
                primary_assignee = assignees[0] if assignees else {}

                # Extract inventors
                inventors = patent.get("inventors", [])

                # Extract CPC classes
                cpcs = patent.get("cpcs", [])
                primary_cpc = cpcs[0] if cpcs else {}

                parsed.append({
                    "patent_number": patent.get("patent_number"),
                    "title": patent.get("patent_title"),
                    "abstract": patent.get("patent_abstract"),
                    "grant_date": self._parse_date(patent.get("patent_date")),
                    "filing_date": self._parse_date(patent.get("app_date")),
                    "patent_type": patent.get("patent_type"),
                    "claims_count": patent.get("patent_num_claims"),
                    "assignee_name": primary_assignee.get("assignee_organization"),
                    "assignee_city": primary_assignee.get("assignee_city"),
                    "assignee_state": primary_assignee.get("assignee_state"),
                    "assignee_country": primary_assignee.get("assignee_country"),
                    "primary_class": primary_cpc.get("cpc_subsection_id"),
                    "inventors": [
                        {
                            "name": f"{inv.get('inventor_first_name', '')} {inv.get('inventor_last_name', '')}".strip(),
                            "city": inv.get("inventor_city"),
                            "state": inv.get("inventor_state"),
                            "country": inv.get("inventor_country"),
                        }
                        for inv in inventors
                    ],
                })
            except Exception as e:
                logger.warning(f"Failed to parse patent: {e}")
                continue

        return parsed

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

    async def store_patents(self, patents: List[Dict]) -> int:
        """Store parsed patents in database.

        Args:
            patents: List of parsed patent dicts

        Returns:
            Number of patents stored
        """
        session = SessionLocal()
        count = 0

        try:
            for pat in patents:
                patent_num = pat.get("patent_number")
                if not patent_num:
                    continue

                # Check if exists
                existing = session.query(Patent).filter_by(
                    patent_number=patent_num
                ).first()

                if existing:
                    continue

                # Create patent record
                patent = Patent(
                    patent_number=patent_num,
                    title=pat.get("title"),
                    abstract=pat.get("abstract"),
                    grant_date=pat.get("grant_date"),
                    filing_date=pat.get("filing_date"),
                    patent_type=pat.get("patent_type"),
                    claims_count=pat.get("claims_count"),
                    primary_class=pat.get("primary_class"),
                    status="granted",
                )
                session.add(patent)

                # Create assignee record
                if pat.get("assignee_name"):
                    assignee = PatentAssignee(
                        patent_number=patent_num,
                        assignee_name=pat["assignee_name"],
                        city=pat.get("assignee_city"),
                        state=pat.get("assignee_state"),
                        country=pat.get("assignee_country"),
                        is_original_assignee=True,
                    )
                    session.add(assignee)

                count += 1

            session.commit()
            logger.info(f"Stored {count} patents")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store patents: {e}")
            raise
        finally:
            session.close()

        return count

    def normalize_company_name(self, name: str) -> str:
        """Normalize company name for matching.

        Args:
            name: Raw company name

        Returns:
            Normalized name
        """
        if not name:
            return ""

        # Convert to uppercase
        name = name.upper()

        # Remove common suffixes (longer ones first to avoid partial matches)
        suffixes = [
            ", CORPORATION", " CORPORATION",
            ", LIMITED", " LIMITED",
            ", INC.", " INC.", ", INC", " INC",
            ", LLC", " LLC",
            ", LTD", " LTD",
            ", CORP.", " CORP.", ", CORP", " CORP",
            ", CO.", " CO.",
        ]
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]

        # Remove extra whitespace
        name = " ".join(name.split())

        return name.strip()

    def get_patent_count_by_company(
        self,
        entity_id: str,
        start_date: date,
        end_date: date,
    ) -> int:
        """Get patent count for company in date range.

        Args:
            entity_id: Company entity ID
            start_date: Start of period
            end_date: End of period

        Returns:
            Patent count
        """
        session = SessionLocal()
        try:
            count = (
                session.query(Patent)
                .join(PatentAssignee, Patent.patent_number == PatentAssignee.patent_number)
                .filter(
                    PatentAssignee.entity_id == entity_id,
                    Patent.grant_date >= start_date,
                    Patent.grant_date <= end_date,
                )
                .count()
            )
            return count
        finally:
            session.close()

    async def run_collection(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """Run full collection cycle.

        Args:
            start_date: Start date (default: 7 days ago)
            end_date: End date (default: today)

        Returns:
            Number of patents stored
        """
        logger.info("Starting USPTO patent collection")

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        try:
            raw_data = await self.fetch_patents_by_date(start_date, end_date)
            if raw_data:
                await self.store_raw(raw_data)

            parsed = self.parse(raw_data)
            count = await self.store_patents(parsed)

            logger.info(f"USPTO collection complete: {count} patents")
            return count

        finally:
            await self.close()

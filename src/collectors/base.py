"""Base collector class for all data sources."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Generic, Optional, TypeVar
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import httpx

from src.core.config import settings

logger = structlog.get_logger()

T = TypeVar("T")


@dataclass
class CollectorResult(Generic[T]):
    """Result from a collector run."""

    success: bool
    data: list[T] = field(default_factory=list)
    error_message: Optional[str] = None
    records_fetched: int = 0
    records_stored: int = 0
    fetch_timestamp: datetime = field(default_factory=datetime.utcnow)
    source_timestamp: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CollectorError(Exception):
    """Base exception for collector errors."""

    pass


class FetchError(CollectorError):
    """Error during data fetching."""

    pass


class ParseError(CollectorError):
    """Error during data parsing."""

    pass


class BaseCollector(ABC):
    """Abstract base class for all data collectors."""

    # Override in subclasses
    name: str = "base"
    source_id: int = 0
    update_frequency: str = "daily"  # continuous, hourly, daily, weekly, monthly

    def __init__(self):
        self.logger = structlog.get_logger().bind(collector=self.name)
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.collector_timeout_seconds),
                follow_redirects=True,
                headers={
                    "User-Agent": f"AltDataPlatform/{settings.app_version}"
                },
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @abstractmethod
    async def fetch(self, **kwargs) -> Any:
        """Fetch raw data from source.

        Should be overridden by subclasses.
        Raises FetchError on failure.
        """
        pass

    @abstractmethod
    async def parse(self, raw_data: Any) -> list[Any]:
        """Parse raw data into structured records.

        Should be overridden by subclasses.
        Raises ParseError on failure.
        """
        pass

    @abstractmethod
    async def store(self, records: list[Any]) -> int:
        """Store parsed records to database.

        Should be overridden by subclasses.
        Returns number of records stored.
        """
        pass

    async def validate(self, records: list[Any]) -> list[Any]:
        """Validate records before storing.

        Can be overridden for custom validation.
        Returns list of valid records.
        """
        return records

    @retry(
        stop=stop_after_attempt(settings.collector_max_retries),
        wait=wait_exponential(
            multiplier=1,
            min=settings.collector_retry_delay_seconds,
            max=60,
        ),
        retry=retry_if_exception_type((FetchError, httpx.HTTPError)),
    )
    async def _fetch_with_retry(self, **kwargs) -> Any:
        """Fetch with automatic retry on failure."""
        return await self.fetch(**kwargs)

    async def collect(self, **kwargs) -> CollectorResult:
        """Main collection pipeline: fetch -> parse -> validate -> store."""
        self.logger.info("Starting collection", **kwargs)
        start_time = datetime.utcnow()

        try:
            # Fetch
            raw_data = await self._fetch_with_retry(**kwargs)
            self.logger.debug("Fetch complete")

            # Parse
            records = await self.parse(raw_data)
            self.logger.debug("Parse complete", record_count=len(records))

            # Validate
            valid_records = await self.validate(records)
            self.logger.debug("Validation complete", valid_count=len(valid_records))

            # Store
            stored_count = await self.store(valid_records)
            self.logger.info(
                "Collection complete",
                records_fetched=len(records),
                records_stored=stored_count,
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
            )

            return CollectorResult(
                success=True,
                data=valid_records,
                records_fetched=len(records),
                records_stored=stored_count,
                fetch_timestamp=start_time,
            )

        except FetchError as e:
            self.logger.error("Fetch failed", error=str(e))
            return CollectorResult(
                success=False,
                error_message=f"Fetch error: {str(e)}",
                fetch_timestamp=start_time,
            )
        except ParseError as e:
            self.logger.error("Parse failed", error=str(e))
            return CollectorResult(
                success=False,
                error_message=f"Parse error: {str(e)}",
                fetch_timestamp=start_time,
            )
        except Exception as e:
            self.logger.exception("Unexpected error during collection")
            return CollectorResult(
                success=False,
                error_message=f"Unexpected error: {str(e)}",
                fetch_timestamp=start_time,
            )
        finally:
            await self.close()

    async def backfill(
        self,
        start_date: date,
        end_date: date,
        **kwargs
    ) -> list[CollectorResult]:
        """Backfill historical data for a date range.

        Can be overridden for source-specific backfill logic.
        """
        self.logger.info(
            "Starting backfill",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        results = []
        current = start_date

        while current <= end_date:
            result = await self.collect(date=current, **kwargs)
            results.append(result)
            current = current.replace(day=current.day + 1) if current.month == (current + 1).month else current.replace(month=current.month + 1, day=1)

        return results

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"

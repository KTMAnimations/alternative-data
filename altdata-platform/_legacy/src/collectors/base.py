"""Base collector class for all data sources."""

import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generic, Optional, TypeVar

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)

RawDataType = TypeVar("RawDataType")
ParsedDataType = TypeVar("ParsedDataType")


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls_per_second: float):
        self.min_interval = 1.0 / calls_per_second
        self.last_call: Optional[float] = None
    
    async def wait(self) -> None:
        """Wait if necessary to respect rate limit."""
        if settings.skip_rate_limits:
            return
        
        if self.last_call is not None:
            elapsed = asyncio.get_event_loop().time() - self.last_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
        
        self.last_call = asyncio.get_event_loop().time()


class BaseCollector(ABC, Generic[RawDataType, ParsedDataType]):
    """Abstract base class for all data collectors.
    
    Provides common functionality for:
    - Rate limiting
    - Raw data storage
    - Logging and error handling
    - Retry logic
    
    Subclasses must implement:
    - fetch(): Retrieve data from source
    - parse(): Transform raw data to structured format
    - SOURCE_NAME: Identifier for the data source
    """
    
    SOURCE_NAME: str = "base"
    DEFAULT_RATE_LIMIT: float = 1.0  # requests per second
    
    def __init__(
        self,
        rate_limit: Optional[float] = None,
        storage_path: Optional[Path] = None,
    ):
        """Initialize the collector.
        
        Args:
            rate_limit: Maximum requests per second (None uses default)
            storage_path: Override path for raw data storage
        """
        self.rate_limiter = RateLimiter(rate_limit or self.DEFAULT_RATE_LIMIT)
        self.storage_path = storage_path or Path(settings.local_storage_path)
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def http_client(self) -> httpx.AsyncClient:
        """Lazy-initialized HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
            )
        return self._http_client
    
    async def close(self) -> None:
        """Close resources."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
    
    @abstractmethod
    async def fetch(self) -> RawDataType:
        """Fetch raw data from the source.
        
        Returns:
            Raw data in source-specific format
            
        Raises:
            CollectorError: If fetch fails
        """
        pass
    
    @abstractmethod
    def parse(self, raw_data: RawDataType) -> ParsedDataType:
        """Parse raw data into structured format.
        
        Args:
            raw_data: Raw data from fetch()
            
        Returns:
            Parsed data ready for storage
            
        Raises:
            ValidationError: If data fails validation
        """
        pass
    
    async def store_raw(
        self,
        data: Any,
        data_timestamp: Optional[datetime] = None,
    ) -> str:
        """Store raw data and return file path.
        
        Args:
            data: Raw data to store
            data_timestamp: Timestamp of the data (not fetch time)
            
        Returns:
            Path to stored file
        """
        now = datetime.utcnow()
        
        # Create directory structure: source/year/month/day/
        dir_path = self.storage_path / self.SOURCE_NAME / now.strftime("%Y/%m/%d")
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # Serialize data
        if isinstance(data, (dict, list)):
            content = json.dumps(data, default=str).encode()
            extension = "json"
        elif isinstance(data, str):
            content = data.encode()
            extension = "txt"
        elif isinstance(data, bytes):
            content = data
            extension = "bin"
        else:
            content = str(data).encode()
            extension = "txt"
        
        # Generate filename with timestamp and hash
        checksum = hashlib.sha256(content).hexdigest()[:16]
        filename = f"{now.strftime('%H%M%S')}_{checksum}.{extension}"
        file_path = dir_path / filename
        
        # Write file
        file_path.write_bytes(content)
        
        logger.info(
            f"Stored raw data",
            extra={
                "source": self.SOURCE_NAME,
                "path": str(file_path),
                "size": len(content),
                "checksum": checksum,
            }
        )
        
        return str(file_path)
    
    async def run(self) -> ParsedDataType:
        """Execute the full collection cycle.
        
        Returns:
            Parsed data from this collection run
        """
        logger.info(f"Starting {self.SOURCE_NAME} collector")
        start_time = datetime.utcnow()
        
        try:
            # Wait for rate limit
            await self.rate_limiter.wait()
            
            # Fetch raw data
            raw_data = await self.fetch()
            
            # Store raw data
            raw_path = await self.store_raw(raw_data)
            
            # Parse data
            parsed_data = self.parse(raw_data)
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Completed {self.SOURCE_NAME} collection",
                extra={
                    "elapsed_seconds": elapsed,
                    "raw_path": raw_path,
                }
            )
            
            return parsed_data
            
        except Exception as e:
            logger.error(
                f"Collection failed for {self.SOURCE_NAME}",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise
        finally:
            await self.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


class CollectorError(Exception):
    """Base exception for collector errors."""
    pass


class RateLimitError(CollectorError):
    """Raised when rate limit is exceeded."""
    pass


class ValidationError(CollectorError):
    """Raised when data validation fails."""
    pass

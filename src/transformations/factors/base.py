"""Base factor computation class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
import structlog

logger = structlog.get_logger()


@dataclass
class FactorResult:
    """Result from factor computation."""

    ticker: str
    factor_id: str
    as_of_date: date
    mean: Decimal
    variance: Decimal
    data_quality: Decimal = Decimal("1.0")
    revision_status: str = "original"
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseFactor(ABC):
    """Abstract base class for factor computations."""

    # Override in subclasses
    factor_id: str = "base"
    name: str = "Base Factor"
    description: str = ""
    domain: str = "unknown"
    primary_entities: list[str] = []

    def __init__(self):
        self.logger = structlog.get_logger().bind(factor=self.factor_id)

    @abstractmethod
    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute factor values for given date and tickers.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers to compute for.
                    If None, compute for all primary entities.

        Returns:
            List of FactorResult objects
        """
        pass

    @abstractmethod
    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        pass

    @abstractmethod
    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        pass

    async def validate_inputs(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> bool:
        """Validate inputs before computation.

        Can be overridden for custom validation.
        """
        if as_of_date > date.today():
            self.logger.warning("Computing factor for future date", date=as_of_date)
            return False
        return True

    async def compute_with_logging(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute with logging and timing."""
        start = datetime.utcnow()
        self.logger.info("Computing factor", as_of_date=as_of_date, tickers=tickers)

        if not await self.validate_inputs(as_of_date, tickers):
            self.logger.error("Input validation failed")
            return []

        try:
            results = await self.compute(as_of_date, tickers)
            duration = (datetime.utcnow() - start).total_seconds()
            self.logger.info(
                "Factor computed",
                result_count=len(results),
                duration_seconds=duration,
            )
            return results
        except Exception as e:
            self.logger.exception("Factor computation failed", error=str(e))
            raise

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(factor_id={self.factor_id})>"

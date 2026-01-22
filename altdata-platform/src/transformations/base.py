"""Base factor computation framework."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.models.database import SessionLocal
from src.models.schemas import Factor, FactorDefinition

logger = logging.getLogger(__name__)


class BaseFactor(ABC):
    """Abstract base class for factor computations.

    Factors are quantitative signals derived from raw data sources.
    Each factor must implement the compute() method to calculate values.
    """

    FACTOR_NAME: str = "base_factor"
    FACTOR_DESCRIPTION: str = ""
    CATEGORY: str = "general"
    ENTITY_TYPE: str = "company"
    FREQUENCY: str = "daily"
    LOOKBACK_DAYS: int = 30

    def __init__(self):
        """Initialize the factor computation."""
        self.session = None

    def _get_session(self):
        """Get or create database session."""
        if self.session is None:
            self.session = SessionLocal()
        return self.session

    def _close_session(self):
        """Close database session."""
        if self.session is not None:
            self.session.close()
            self.session = None

    @abstractmethod
    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        **kwargs
    ) -> Optional[float]:
        """Compute the factor value for an entity at a given date.

        Args:
            entity_id: Entity identifier (e.g., ticker)
            as_of_date: Date for which to compute the factor
            **kwargs: Additional computation parameters

        Returns:
            Factor value or None if cannot be computed
        """
        pass

    def compute_and_store(
        self,
        entity_id: str,
        as_of_date: datetime,
        **kwargs
    ) -> Optional[Factor]:
        """Compute factor and store in database.

        Args:
            entity_id: Entity identifier
            as_of_date: Date for computation
            **kwargs: Additional parameters

        Returns:
            Stored Factor record or None
        """
        try:
            value = self.compute(entity_id, as_of_date, **kwargs)

            if value is None:
                logger.warning(
                    f"Could not compute {self.FACTOR_NAME} for {entity_id} on {as_of_date}"
                )
                return None

            session = self._get_session()

            # Check for existing factor value
            existing = (
                session.query(Factor)
                .filter_by(
                    factor_name=self.FACTOR_NAME,
                    entity_id=entity_id,
                    effective_date=as_of_date,
                )
                .first()
            )

            if existing:
                existing.value = value
                existing.computed_at = datetime.utcnow()
                existing.version += 1
                factor = existing
            else:
                factor = Factor(
                    factor_name=self.FACTOR_NAME,
                    entity_id=entity_id,
                    entity_type=self.ENTITY_TYPE,
                    value=value,
                    effective_date=as_of_date,
                    computed_at=datetime.utcnow(),
                    version=1,
                )
                session.add(factor)

            session.commit()

            # Refresh to ensure all attributes are loaded before detaching
            session.refresh(factor)

            # Extract values before closing session
            result_factor = Factor(
                id=factor.id,
                factor_name=factor.factor_name,
                entity_id=factor.entity_id,
                entity_type=factor.entity_type,
                value=factor.value,
                effective_date=factor.effective_date,
                computed_at=factor.computed_at,
                version=factor.version,
            )

            logger.info(
                f"Stored {self.FACTOR_NAME}={value:.4f} for {entity_id} on {as_of_date}"
            )
            return result_factor

        except Exception as e:
            logger.error(f"Error computing/storing {self.FACTOR_NAME}: {e}")
            if self.session:
                self.session.rollback()
            raise
        finally:
            self._close_session()

    def get_definition(self) -> Dict[str, Any]:
        """Get factor definition metadata.

        Returns:
            Factor definition dict
        """
        return {
            "id": self.FACTOR_NAME,
            "name": self.FACTOR_NAME.replace("_", " ").title(),
            "description": self.FACTOR_DESCRIPTION,
            "category": self.CATEGORY,
            "entity_type": self.ENTITY_TYPE,
            "frequency": self.FREQUENCY,
            "lookback_days": self.LOOKBACK_DAYS,
        }

    def register_definition(self) -> FactorDefinition:
        """Register factor definition in database.

        Returns:
            FactorDefinition record
        """
        session = self._get_session()
        try:
            definition = session.query(FactorDefinition).filter_by(
                id=self.FACTOR_NAME
            ).first()

            if not definition:
                definition = FactorDefinition(
                    id=self.FACTOR_NAME,
                    name=self.FACTOR_NAME.replace("_", " ").title(),
                    description=self.FACTOR_DESCRIPTION,
                    category=self.CATEGORY,
                    entity_type=self.ENTITY_TYPE,
                    frequency=self.FREQUENCY,
                    lookback_days=self.LOOKBACK_DAYS,
                )
                session.add(definition)
                session.commit()

            return definition
        finally:
            self._close_session()


class FactorRegistry:
    """Registry for all available factor implementations."""

    _factors: Dict[str, type] = {}

    @classmethod
    def register(cls, factor_class: type) -> type:
        """Register a factor class.

        Args:
            factor_class: Factor implementation class

        Returns:
            The registered class (for use as decorator)
        """
        cls._factors[factor_class.FACTOR_NAME] = factor_class
        return factor_class

    @classmethod
    def get(cls, factor_name: str) -> Optional[type]:
        """Get a factor class by name.

        Args:
            factor_name: Factor identifier

        Returns:
            Factor class or None
        """
        return cls._factors.get(factor_name)

    @classmethod
    def get_all(cls) -> Dict[str, type]:
        """Get all registered factors.

        Returns:
            Dict mapping factor names to classes
        """
        return cls._factors.copy()

    @classmethod
    def list_factors(cls) -> List[Dict[str, Any]]:
        """List all factor definitions.

        Returns:
            List of factor definition dicts
        """
        return [
            factor_class().get_definition()
            for factor_class in cls._factors.values()
        ]

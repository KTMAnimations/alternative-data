"""Factor models for derived signals."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class FactorDomain(str, Enum):
    """Domain categories for factors."""

    TRAVEL = "travel"
    REAL_ESTATE = "real_estate"
    ENERGY = "energy"
    GAMING = "gaming"
    GOVERNMENT = "government"
    INFRASTRUCTURE = "infrastructure"
    ENTERTAINMENT = "entertainment"
    INTERNET = "internet"
    COMPOSITE = "composite"


class RelationshipType(str, Enum):
    """Types of relationships between factors."""

    DERIVED_FROM = "derived-from"
    CORRELATED_WITH = "correlated-with"
    CAUSES = "causes"
    LEADS = "leads"
    COMPONENT_OF = "component-of"


class Factor(Base, TimestampMixin):
    """Factor definitions with metadata and documentation."""

    __tablename__ = "factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factor_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[FactorDomain] = mapped_column(SQLEnum(FactorDomain), nullable=False)
    source_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("data_sources.id"), nullable=True
    )

    # Formula and computation
    formula: Mapped[str] = mapped_column(Text, nullable=False)  # LaTeX format
    formula_description: Mapped[str] = mapped_column(Text, nullable=False)
    computation_frequency: Mapped[str] = mapped_column(String(20), nullable=False)

    # Academic documentation
    economic_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    literature_references: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    signal_interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    known_limitations: Mapped[str] = mapped_column(Text, nullable=True)

    # Target entities
    primary_entities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    secondary_entities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Historical performance metrics
    historical_ic: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    historical_ir: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    historical_tstat: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    historical_hit_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)

    # Decay analysis (IC at different horizons)
    decay_1d: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    decay_5d: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    decay_10d: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    decay_21d: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    decay_63d: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    estimated_half_life_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    # Relationships
    values = relationship("FactorValue", back_populates="factor", lazy="dynamic")


class FactorValue(Base, TimestampMixin):
    """Point-in-time factor values with probabilistic output."""

    __tablename__ = "factor_values"
    __table_args__ = (
        UniqueConstraint("factor_id", "ticker", "as_of_date", name="uq_factor_value"),
        Index("ix_factor_values_factor_date", "factor_id", "as_of_date"),
        Index("ix_factor_values_ticker_date", "ticker", "as_of_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factor_id: Mapped[int] = mapped_column(Integer, ForeignKey("factors.id"), nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Probabilistic output (mean + variance)
    mean: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    variance: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    # Data quality
    data_quality: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1.0)
    revision_status: Mapped[str] = mapped_column(String(20), default="original")

    # Computation metadata
    computation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    input_data_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    factor = relationship("Factor", back_populates="values")


class FactorRelationship(Base, TimestampMixin):
    """Relationships between factors for graph visualization."""

    __tablename__ = "factor_relationships"
    __table_args__ = (
        UniqueConstraint("source_factor_id", "target_factor_id", "relationship_type",
                        name="uq_factor_relationship"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_factor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factors.id"), nullable=False
    )
    target_factor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factors.id"), nullable=False
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        SQLEnum(RelationshipType), nullable=False
    )
    strength: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CustomFactorBlend(Base, TimestampMixin):
    """Custom factor blends created by users."""

    __tablename__ = "custom_factor_blends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Blend configuration
    component_factors: Mapped[list] = mapped_column(JSON, nullable=False)  # List of factor_ids
    weights: Mapped[list] = mapped_column(JSON, nullable=False)  # Corresponding weights
    optimization_objective: Mapped[str] = mapped_column(String(50), nullable=True)
    constraints: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Performance metrics
    blended_ic: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    blended_ir: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExperimentStatus(str, Enum):
    """Status of an A/B experiment."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    PROMOTED = "promoted"


class Experiment(Base, TimestampMixin):
    """A/B experiment for comparing factor formulations."""

    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Control and treatment factors
    control_factor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factors.id"), nullable=False
    )
    treatment_factor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factors.id"), nullable=False
    )

    # Experiment period
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Status
    status: Mapped[ExperimentStatus] = mapped_column(
        SQLEnum(ExperimentStatus), default=ExperimentStatus.DRAFT
    )

    # Performance tracking
    control_ic: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    treatment_ic: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    control_ir: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    treatment_ir: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)

    # Statistical significance
    p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8), nullable=True)
    is_significant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    significance_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0.05)

    # Winner determination
    winner: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "control" or "treatment"
    promoted_factor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("factors.id"), nullable=True
    )

    # Metrics history (JSON array of daily metrics)
    metrics_history: Mapped[list] = mapped_column(JSON, default=list)

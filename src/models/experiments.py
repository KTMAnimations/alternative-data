"""A/B Experiment models for factor testing (US-021)."""

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class ExperimentStatus(str, Enum):
    """Status of an A/B experiment."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Experiment(Base, TimestampMixin):
    """A/B experiment for comparing factor formulations."""

    __tablename__ = "experiments"
    __table_args__ = (
        Index("ix_experiments_status", "status"),
        Index("ix_experiments_user", "user_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # User ownership
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Control factor (baseline)
    control_factor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factors.id"), nullable=False
    )

    # Treatment factor (variant being tested)
    treatment_factor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factors.id"), nullable=False
    )

    # Experiment configuration
    status: Mapped[ExperimentStatus] = mapped_column(
        SQLEnum(ExperimentStatus), default=ExperimentStatus.DRAFT
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Target entities for evaluation
    target_tickers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Experiment parameters
    min_sample_size: Mapped[int] = mapped_column(Integer, default=100)
    significance_level: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.05")
    )  # Alpha for p-value threshold

    # Results - Control metrics
    control_ic: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    control_ir: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    control_tstat: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    control_hit_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    control_sharpe: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    # Results - Treatment metrics
    treatment_ic: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    treatment_ir: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    treatment_tstat: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    treatment_hit_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    treatment_sharpe: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    # Statistical significance results
    p_value_ic: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    p_value_ir: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    is_significant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    confidence_interval_lower: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 6), nullable=True
    )
    confidence_interval_upper: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 6), nullable=True
    )

    # Sample sizes
    control_sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    treatment_sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Winner determination
    winner: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # 'control', 'treatment', 'inconclusive'
    winner_promoted: Mapped[bool] = mapped_column(Boolean, default=False)
    promoted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Time series data for visualization
    daily_metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    control_factor = relationship("Factor", foreign_keys=[control_factor_id])
    treatment_factor = relationship("Factor", foreign_keys=[treatment_factor_id])
    user = relationship("User", back_populates="experiments")


class ExperimentMetricSnapshot(Base, TimestampMixin):
    """Daily metric snapshots for experiment tracking."""

    __tablename__ = "experiment_metric_snapshots"
    __table_args__ = (
        Index("ix_experiment_snapshots", "experiment_id", "snapshot_date"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("experiments.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Control metrics
    control_ic: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    control_ir: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    control_hit_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    control_sample_count: Mapped[int] = mapped_column(Integer, default=0)

    # Treatment metrics
    treatment_ic: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    treatment_ir: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    treatment_hit_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    treatment_sample_count: Mapped[int] = mapped_column(Integer, default=0)

    # Running p-value
    running_p_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)

    # Relationship
    experiment = relationship("Experiment")

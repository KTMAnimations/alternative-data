"""Database models for USPTO Patent data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Boolean, Index, JSON, Text, Date
)

from src.models.database import Base


class Patent(Base):
    """Patent application and grant records."""
    __tablename__ = "patents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patent_number = Column(String(20), unique=True, index=True)
    application_number = Column(String(20), index=True)
    patent_type = Column(String(50))  # utility, design, plant
    title = Column(Text)
    abstract = Column(Text)
    filing_date = Column(Date, index=True)
    grant_date = Column(Date, index=True)
    publication_date = Column(Date)
    status = Column(String(50))  # pending, granted, abandoned
    primary_class = Column(String(20), index=True)  # CPC/USPC classification
    secondary_classes = Column(JSON)  # List of additional classes
    claims_count = Column(Integer)
    independent_claims_count = Column(Integer)
    raw_data_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_patent_filing", "filing_date"),
        Index("ix_patent_grant", "grant_date"),
        Index("ix_patent_class", "primary_class"),
    )


class PatentAssignee(Base):
    """Patent assignee (owner) records."""
    __tablename__ = "patent_assignees"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patent_number = Column(String(20), nullable=False, index=True)
    assignee_name = Column(String(500), nullable=False)
    assignee_type = Column(String(50))  # corporation, individual, government
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(100))
    entity_id = Column(String(50), index=True)  # Mapped company entity ID
    assignment_date = Column(Date)
    is_original_assignee = Column(Boolean, default=True)

    __table_args__ = (
        Index("ix_assignee_entity", "entity_id"),
        Index("ix_assignee_name", "assignee_name"),
    )


class PatentInventor(Base):
    """Patent inventor records."""
    __tablename__ = "patent_inventors"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patent_number = Column(String(20), nullable=False, index=True)
    inventor_name = Column(String(255), nullable=False)
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(100))
    sequence_number = Column(Integer)  # First inventor, second, etc.

    __table_args__ = (
        Index("ix_inventor_name", "inventor_name"),
    )


class PatentCitation(Base):
    """Patent citation relationships."""
    __tablename__ = "patent_citations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    citing_patent = Column(String(20), nullable=False, index=True)
    cited_patent = Column(String(20), nullable=False, index=True)
    citation_type = Column(String(50))  # patent, application, foreign
    is_examiner_citation = Column(Boolean)  # vs applicant citation

    __table_args__ = (
        Index("ix_citation_citing", "citing_patent"),
        Index("ix_citation_cited", "cited_patent"),
    )


class PatentClassification(Base):
    """Patent classification lookup."""
    __tablename__ = "patent_classifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    class_code = Column(String(20), unique=True, nullable=False, index=True)
    class_type = Column(String(20))  # CPC, USPC, IPC
    title = Column(String(500))
    parent_class = Column(String(20))
    level = Column(Integer)  # Hierarchy level (section, class, subclass, etc.)

    __table_args__ = (
        Index("ix_class_parent", "parent_class"),
    )


class PatentApplication(Base):
    """Pre-grant patent applications."""
    __tablename__ = "patent_applications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    application_number = Column(String(20), unique=True, nullable=False, index=True)
    publication_number = Column(String(20), index=True)
    title = Column(Text)
    abstract = Column(Text)
    filing_date = Column(Date, index=True)
    publication_date = Column(Date)
    status = Column(String(50))  # pending, granted, abandoned
    primary_class = Column(String(20))
    assignee_name = Column(String(500))
    entity_id = Column(String(50), index=True)
    claims_count = Column(Integer)
    raw_data_id = Column(BigInteger)

    __table_args__ = (
        Index("ix_app_entity", "entity_id"),
        Index("ix_app_filing", "filing_date"),
    )

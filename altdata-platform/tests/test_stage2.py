"""Stage 2 Tests: Database models and schema verification."""

import pytest
from datetime import datetime
from sqlalchemy import inspect


def test_tables_created():
    """Verify all tables exist."""
    from src.models.database import engine

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "raw_data_catalog" in tables
    assert "factors" in tables
    assert "entities" in tables
    assert "sec_form4_transactions" in tables
    assert "fred_series" in tables
    assert "sec_filings" in tables
    assert "factor_definitions" in tables
    assert "api_keys" in tables


def test_can_insert_entity():
    """Verify entity insertion works."""
    from src.models.database import SessionLocal
    from src.models.schemas import Entity

    session = SessionLocal()
    try:
        # Clean up if exists from previous test
        existing = session.query(Entity).filter_by(id="AAPL_TEST").first()
        if existing:
            session.delete(existing)
            session.commit()

        entity = Entity(
            id="AAPL_TEST",
            entity_type="company",
            name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193"
        )
        session.add(entity)
        session.commit()

        result = session.query(Entity).filter_by(id="AAPL_TEST").first()
        assert result.name == "Apple Inc."
        assert result.ticker == "AAPL"
        assert result.cik == "0000320193"

        session.delete(result)
        session.commit()
    finally:
        session.close()


def test_can_insert_factor():
    """Verify factor insertion works."""
    from src.models.database import SessionLocal
    from src.models.schemas import Factor

    session = SessionLocal()
    try:
        factor = Factor(
            factor_name="test_factor",
            entity_id="AAPL",
            entity_type="company",
            value=123.45,
            effective_date=datetime(2024, 1, 15),
            computed_at=datetime.utcnow(),
            version=1
        )
        session.add(factor)
        session.commit()

        result = session.query(Factor).filter_by(
            factor_name="test_factor",
            entity_id="AAPL"
        ).first()
        assert result.value == 123.45
        assert result.version == 1

        session.delete(result)
        session.commit()
    finally:
        session.close()


def test_can_insert_raw_data_catalog():
    """Verify raw data catalog insertion works."""
    from src.models.database import SessionLocal
    from src.models.schemas import RawDataCatalog

    session = SessionLocal()
    try:
        record = RawDataCatalog(
            source="sec_edgar",
            file_path="/data/raw/sec_edgar/2024/01/15/test.json",
            fetch_timestamp=datetime.utcnow(),
            data_timestamp=datetime(2024, 1, 15),
            checksum="abc123def456",
            record_count=100,
            file_size_bytes=1024
        )
        session.add(record)
        session.commit()

        result = session.query(RawDataCatalog).filter_by(
            source="sec_edgar",
            checksum="abc123def456"
        ).first()
        assert result.record_count == 100
        assert result.file_size_bytes == 1024

        session.delete(result)
        session.commit()
    finally:
        session.close()


def test_can_insert_sec_form4():
    """Verify SEC Form 4 insertion works."""
    from src.models.database import SessionLocal
    from src.models.schemas import SECForm4Transaction

    session = SessionLocal()
    try:
        # Clean up if exists
        existing = session.query(SECForm4Transaction).filter_by(
            accession_number="0001234567-24-000001"
        ).first()
        if existing:
            session.delete(existing)
            session.commit()

        transaction = SECForm4Transaction(
            accession_number="0001234567-24-000001",
            cik="0001234567",
            issuer_cik="0001318605",
            issuer_name="Tesla, Inc.",
            ticker="TSLA",
            insider_name="Musk Elon",
            insider_title="CEO",
            transaction_type="P",
            shares=10000,
            price_per_share=250.00,
            total_value=2500000.00,
            transaction_date=datetime(2024, 1, 15),
            filed_date=datetime(2024, 1, 16)
        )
        session.add(transaction)
        session.commit()

        result = session.query(SECForm4Transaction).filter_by(
            accession_number="0001234567-24-000001"
        ).first()
        assert result.ticker == "TSLA"
        assert result.shares == 10000
        assert result.transaction_type == "P"

        session.delete(result)
        session.commit()
    finally:
        session.close()


def test_can_insert_fred_series():
    """Verify FRED series insertion works."""
    from src.models.database import SessionLocal
    from src.models.schemas import FREDSeries

    session = SessionLocal()
    try:
        # Clean up if exists
        existing = session.query(FREDSeries).filter_by(
            series_id="GS10",
            observation_date=datetime(2024, 1, 15)
        ).first()
        if existing:
            session.delete(existing)
            session.commit()

        series = FREDSeries(
            series_id="GS10",
            observation_date=datetime(2024, 1, 15),
            value=4.12,
            realtime_start=datetime(2024, 1, 26),
            realtime_end=datetime(2024, 1, 26)
        )
        session.add(series)
        session.commit()

        result = session.query(FREDSeries).filter_by(
            series_id="GS10",
            observation_date=datetime(2024, 1, 15)
        ).first()
        assert result.value == 4.12

        session.delete(result)
        session.commit()
    finally:
        session.close()


def test_entity_indexes_exist():
    """Verify important indexes are created."""
    from src.models.database import engine
    from sqlalchemy import inspect

    inspector = inspect(engine)

    # Check entities table indexes
    entity_indexes = inspector.get_indexes("entities")
    index_names = [idx["name"] for idx in entity_indexes]

    # Should have index on ticker
    assert any("ticker" in name for name in index_names)

    # Check factors table indexes
    factor_indexes = inspector.get_indexes("factors")
    factor_index_names = [idx["name"] for idx in factor_indexes]

    assert any("factor_name" in str(idx) or "entity" in str(idx)
               for idx in factor_indexes)

#!/usr/bin/env python3
"""Initialize the database with tables and seed data."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import settings
from src.models.database import engine, Base, get_db_session
from src.models.schemas import Entity, FactorDefinition


def create_tables():
    """Create all database tables."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")


def create_hypertables():
    """Create TimescaleDB hypertables for time-series tables.

    This must be called AFTER create_tables() since the tables must exist first.
    """
    print("Creating TimescaleDB hypertables...")

    # Tables that should be hypertables with their time column
    hypertable_configs = [
        ("factors", "effective_date"),
        ("flight_positions", "timestamp"),
        ("grid_load", "timestamp"),
        ("grid_prices", "timestamp"),
        ("generation_mix", "timestamp"),
        ("air_quality_measurements", "timestamp"),
    ]

    from sqlalchemy import text

    with engine.connect() as conn:
        # Check if TimescaleDB is available
        try:
            result = conn.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"))
            row = result.fetchone()
            if not row:
                print("  TimescaleDB extension not installed, skipping hypertables")
                return
            print(f"  TimescaleDB version: {row[0]}")
        except Exception as e:
            print(f"  TimescaleDB not available: {e}")
            return

        for table_name, time_column in hypertable_configs:
            try:
                # Check if table exists
                result = conn.execute(text(
                    f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')"
                ))
                if not result.fetchone()[0]:
                    print(f"  Table '{table_name}' does not exist, skipping")
                    continue

                # Check if already a hypertable
                result = conn.execute(text(
                    f"SELECT EXISTS (SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = '{table_name}')"
                ))
                if result.fetchone()[0]:
                    print(f"  '{table_name}' is already a hypertable")
                    continue

                # Create hypertable
                conn.execute(text(
                    f"SELECT create_hypertable('{table_name}', '{time_column}', if_not_exists => TRUE, migrate_data => TRUE)"
                ))
                conn.commit()
                print(f"  Created hypertable: {table_name} (partitioned by {time_column})")

            except Exception as e:
                print(f"  Warning: Could not create hypertable for '{table_name}': {e}")
                conn.rollback()

    print("Hypertable creation complete!")


def seed_entities():
    """Seed sample entities."""
    print("Seeding sample entities...")
    
    entities = [
        Entity(
            id="AAPL",
            entity_type="company",
            name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            sector="Technology",
            industry="Consumer Electronics",
        ),
        Entity(
            id="TSLA",
            entity_type="company",
            name="Tesla, Inc.",
            ticker="TSLA",
            cik="0001318605",
            sector="Consumer Cyclical",
            industry="Auto Manufacturers",
        ),
        Entity(
            id="MSFT",
            entity_type="company",
            name="Microsoft Corporation",
            ticker="MSFT",
            cik="0000789019",
            sector="Technology",
            industry="Software - Infrastructure",
        ),
        Entity(
            id="GOOGL",
            entity_type="company",
            name="Alphabet Inc.",
            ticker="GOOGL",
            cik="0001652044",
            sector="Communication Services",
            industry="Internet Content & Information",
        ),
        Entity(
            id="AMZN",
            entity_type="company",
            name="Amazon.com, Inc.",
            ticker="AMZN",
            cik="0001018724",
            sector="Consumer Cyclical",
            industry="Internet Retail",
        ),
    ]
    
    with get_db_session() as session:
        for entity in entities:
            existing = session.query(Entity).filter_by(id=entity.id).first()
            if not existing:
                session.add(entity)
        session.commit()
    
    print(f"Seeded {len(entities)} entities.")


def seed_factor_definitions():
    """Seed factor definitions."""
    print("Seeding factor definitions...")
    
    factors = [
        # SEC Factors
        FactorDefinition(
            id="insider_transaction_momentum",
            name="Insider Transaction Momentum",
            description="Net insider buying/selling from Form 4 filings over 30 days",
            category="sec",
            entity_type="company",
            frequency="daily",
            lookback_days=30,
            dependencies=["sec_form4_transactions"],
        ),
        FactorDefinition(
            id="insider_clustering_score",
            name="Insider Clustering Score",
            description="Number of unique insiders trading in same direction within 7 days",
            category="sec",
            entity_type="company",
            frequency="daily",
            lookback_days=7,
            dependencies=["sec_form4_transactions"],
        ),
        FactorDefinition(
            id="8k_event_velocity",
            name="8-K Event Velocity",
            description="Number of 8-K filings in rolling 30-day window",
            category="sec",
            entity_type="company",
            frequency="daily",
            lookback_days=30,
            dependencies=["sec_filings"],
        ),
        FactorDefinition(
            id="filing_delay_score",
            name="Filing Delay Score",
            description="Days between period end and filing date",
            category="sec",
            entity_type="company",
            frequency="quarterly",
            dependencies=["sec_filings"],
        ),
        
        # Macro Factors
        FactorDefinition(
            id="yield_curve_slope",
            name="Yield Curve Slope",
            description="10Y Treasury minus 2Y Treasury yield",
            category="macro",
            entity_type="market",
            frequency="daily",
            dependencies=["fred_series:GS10", "fred_series:GS2"],
        ),
        FactorDefinition(
            id="credit_spread_index",
            name="Credit Spread Index",
            description="BAA corporate bond spread over 10Y Treasury",
            category="macro",
            entity_type="market",
            frequency="daily",
            dependencies=["fred_series:BAA10Y"],
        ),
        FactorDefinition(
            id="recession_probability",
            name="Recession Probability",
            description="Smoothed US Recession Probability from FRED",
            category="macro",
            entity_type="market",
            frequency="monthly",
            dependencies=["fred_series:RECPROUSM156N"],
        ),
        FactorDefinition(
            id="financial_conditions_index",
            name="Financial Conditions Index",
            description="Chicago Fed National Financial Conditions Index",
            category="macro",
            entity_type="market",
            frequency="weekly",
            dependencies=["fred_series:NFCI"],
        ),
    ]
    
    with get_db_session() as session:
        for factor in factors:
            existing = session.query(FactorDefinition).filter_by(id=factor.id).first()
            if not existing:
                session.add(factor)
        session.commit()
    
    print(f"Seeded {len(factors)} factor definitions.")


def main():
    """Run database initialization."""
    print(f"Initializing database: {settings.database_url}")
    print("-" * 50)

    try:
        create_tables()
        create_hypertables()
        seed_entities()
        seed_factor_definitions()

        print("-" * 50)
        print("Database initialization complete!")

    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

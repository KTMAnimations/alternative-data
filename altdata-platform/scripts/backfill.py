#!/usr/bin/env python3
"""
Historical Data Backfill Script

This script backfills historical data from all collectors and computes
factors for backtesting purposes.

Usage:
    python scripts/backfill.py --source sec_edgar --start 2024-01-01 --end 2024-06-30
    python scripts/backfill.py --source all --start 2024-01-01 --end 2024-06-30
    python scripts/backfill.py --factors-only --start 2024-01-01 --end 2024-06-30
"""

import argparse
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import settings
from src.models.database import get_db_session, engine
from src.models.schemas import Entity, Factor, RawDataCatalog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ===========================================
# COLLECTOR IMPORTS
# ===========================================

def get_collector(source: str):
    """Get collector instance by source name."""
    collectors = {
        "sec_edgar": lambda: _get_sec_collector(),
        "fred": lambda: _get_fred_collector(),
        "adsb_exchange": lambda: _get_adsb_collector(),
        "caiso": lambda: _get_caiso_collector(),
        "ercot": lambda: _get_ercot_collector(),
        "pjm": lambda: _get_pjm_collector(),
        "miso": lambda: _get_miso_collector(),
        "uspto": lambda: _get_uspto_collector(),
        "openaq": lambda: _get_openaq_collector(),
    }
    
    if source not in collectors:
        raise ValueError(f"Unknown source: {source}. Available: {list(collectors.keys())}")
    
    return collectors[source]()


def _get_sec_collector():
    from src.collectors.sec_edgar import SECEdgarCollector
    return SECEdgarCollector(user_agent=settings.sec_edgar_user_agent)


def _get_fred_collector():
    from src.collectors.fred import FREDCollector
    return FREDCollector(api_key=settings.fred_api_key)


def _get_adsb_collector():
    from src.collectors.adsb_exchange import ADSBExchangeCollector
    return ADSBExchangeCollector(
        api_key=settings.adsb_exchange_api_key,
        rapidapi_key=settings.adsb_exchange_rapidapi_key
    )


def _get_caiso_collector():
    from src.collectors.power_grid import CAISOCollector
    return CAISOCollector()


def _get_ercot_collector():
    from src.collectors.power_grid import ERCOTCollector
    return ERCOTCollector()


def _get_pjm_collector():
    from src.collectors.power_grid import PJMCollector
    return PJMCollector()


def _get_miso_collector():
    from src.collectors.power_grid import MISOCollector
    return MISOCollector()


def _get_uspto_collector():
    from src.collectors.uspto import USPTOCollector
    return USPTOCollector(api_key=settings.uspto_api_key)


def _get_openaq_collector():
    from src.collectors.openaq import OpenAQCollector
    return OpenAQCollector(api_key=settings.openaq_api_key)


# ===========================================
# BACKFILL FUNCTIONS
# ===========================================

async def backfill_sec_edgar(start_date: date, end_date: date):
    """Backfill SEC EDGAR filings and Form 4 data.

    Note: SEC RSS feeds only provide recent filings (typically last 24-48 hours).
    Historical backfilling would require bulk data downloads from SEC.
    This function fetches recent Form 4s and filters to tracked entities.
    """
    logger.info(f"Backfilling SEC EDGAR (fetching recent Form 4s)")
    logger.info(f"  Note: SEC RSS only provides recent filings, not historical data")

    collector = _get_sec_collector()

    # Get list of entities to backfill
    with get_db_session() as session:
        entities = session.query(Entity).filter(
            Entity.cik.isnot(None)
        ).all()
        entity_ciks = {e.cik.lstrip("0"): e.id for e in entities}

    logger.info(f"  Tracking {len(entity_ciks)} companies")

    total_stored = 0
    try:
        async with collector:
            # Fetch recent Form 4s (SEC RSS only has recent filings)
            filings = await collector.fetch_recent_form4s(limit=100)

            logger.info(f"  Fetched {len(filings)} recent Form 4 filings")

            for filing in filings:
                try:
                    # Get CIK from filing
                    issuer = filing.get("issuer", {})
                    cik = issuer.get("cik", "").lstrip("0")

                    # Check if this is a tracked entity
                    if cik not in entity_ciks:
                        continue

                    entity_id = entity_ciks[cik]

                    # Store transactions
                    transactions = filing.get("transactions", [])
                    for txn in transactions:
                        await store_form4_transaction({
                            "entity_id": entity_id,
                            "cik": cik,
                            "insider_name": filing.get("reporting_owner", {}).get("name"),
                            "insider_title": filing.get("reporting_owner", {}).get("relationship", {}).get("officer_title"),
                            "transaction_date": txn.get("transaction_date"),
                            "transaction_type": txn.get("transaction_code"),
                            "shares": txn.get("shares"),
                            "price_per_share": txn.get("price_per_share"),
                            "shares_owned_after": txn.get("shares_owned_following"),
                        })
                        total_stored += 1

                except Exception as e:
                    logger.warning(f"  Error processing filing: {e}")
                    continue

    except Exception as e:
        logger.error(f"SEC EDGAR backfill error: {e}")

    logger.info(f"SEC EDGAR backfill complete: {total_stored} transactions stored")
    return total_stored


async def backfill_fred(start_date: date, end_date: date):
    """Backfill FRED economic series."""
    logger.info(f"Backfilling FRED from {start_date} to {end_date}")

    collector = _get_fred_collector()

    # Key series to backfill
    SERIES = [
        "GS10", "GS2",           # Treasury yields
        "BAA10Y",                # Credit spread
        "M2SL",                  # Money supply
        "ICSA", "IC4WSA",        # Jobless claims
        "NFCI",                  # Financial conditions
        "T10YIE",                # Inflation expectations
        "RECPROUSM156N",         # Recession probability
        "DFF",                   # Fed funds rate
        "UNRATE",                # Unemployment rate
    ]

    total_observations = 0

    try:
        for series_id in SERIES:
            try:
                logger.info(f"  Fetching {series_id}...")

                # Convert date to datetime for the collector
                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.min.time())

                # fetch_series returns raw API response Dict
                response = await collector.fetch_series(
                    series_id=series_id,
                    start_date=start_dt,
                    end_date=end_dt
                )

                # Parse the response to get observation list
                observations = collector.parse_series_response(response, series_id)

                if not observations:
                    logger.info(f"  {series_id}: No observations")
                    continue

                # Store to database
                with get_db_session() as session:
                    from src.models.schemas import FREDSeries

                    stored_count = 0
                    for obs in observations:
                        # Check if exists
                        existing = session.query(FREDSeries).filter(
                            FREDSeries.series_id == series_id,
                            FREDSeries.observation_date == obs["date"]
                        ).first()

                        if not existing:
                            record = FREDSeries(
                                series_id=series_id,
                                observation_date=obs["date"],
                                value=obs["value"],
                                realtime_start=obs.get("realtime_start"),
                                realtime_end=obs.get("realtime_end"),
                            )
                            session.add(record)
                            stored_count += 1

                    session.commit()

                total_observations += stored_count
                logger.info(f"  {series_id}: {stored_count} new observations (of {len(observations)} fetched)")

            except Exception as e:
                logger.error(f"  Error fetching {series_id}: {e}")

    finally:
        await collector.close()

    logger.info(f"FRED backfill complete: {total_observations} observations")
    return total_observations


async def backfill_power_grid(start_date: date, end_date: date):
    """Backfill power grid data from all ISOs.

    Note: Power grid collectors only support real-time data fetching.
    Historical backfill fetches current snapshots - for true historical data,
    use ISO-specific historical data downloads.
    """
    logger.info(f"Backfilling Power Grid from {start_date} to {end_date}")
    logger.warning("Power grid collectors only fetch real-time data. "
                   "Fetching current snapshot for each ISO.")

    ISOS = ["caiso", "ercot", "pjm", "miso"]
    total_records = 0

    for iso in ISOS:
        try:
            logger.info(f"  Fetching current data for {iso.upper()}...")
            collector = get_collector(iso)

            try:
                # fetch_load() takes no parameters - fetches current real-time data
                load_data = await collector.fetch_load()

                if load_data and load_data.get("load_mw"):
                    # Store to database
                    with get_db_session() as session:
                        from src.models.power_grid import GridLoad

                        load = GridLoad(
                            iso_region=iso.upper(),
                            timestamp=load_data.get("timestamp", datetime.utcnow()),
                            load_mw=load_data.get("load_mw"),
                            forecast_mw=load_data.get("forecast_mw"),
                            capacity_mw=load_data.get("capacity_mw"),
                            load_pct_of_capacity=load_data.get("load_pct_of_capacity"),
                        )
                        session.add(load)
                        session.commit()

                    total_records += 1
                    logger.info(f"  {iso.upper()}: {load_data.get('load_mw')} MW")
                else:
                    logger.warning(f"  {iso.upper()}: No data returned")

            except Exception as e:
                logger.warning(f"    Error fetching {iso.upper()}: {e}")

            finally:
                await collector.close()

        except Exception as e:
            logger.error(f"  Error with {iso}: {e}")

    logger.info(f"Power Grid backfill complete: {total_records} records")
    return total_records


async def backfill_patents(start_date: date, end_date: date):
    """Backfill USPTO patent data."""
    logger.info(f"Backfilling USPTO Patents from {start_date} to {end_date}")

    collector = _get_uspto_collector()

    # Get companies to backfill - extract values to avoid DetachedInstanceError
    with get_db_session() as session:
        entities_query = session.query(Entity).filter(
            Entity.entity_type == "company"
        ).all()
        # Extract values while session is open to avoid DetachedInstanceError
        entities = [
            {"id": e.id, "name": e.name, "ticker": e.ticker}
            for e in entities_query
        ]

    total_patents = 0

    try:
        for entity in entities:
            try:
                # Search by company name using correct method name and parameter
                response = await collector.fetch_patents_by_assignee(
                    assignee_name=entity["name"]
                )

                # Parse the response to get patent list
                patents = collector.parse(response)

                # Store patents
                if patents:
                    with get_db_session() as session:
                        from src.models.patents import Patent, PatentAssignee

                        for patent in patents:
                            patent_num = patent.get("patent_number")
                            if not patent_num:
                                continue

                            existing = session.query(Patent).filter(
                                Patent.patent_number == patent_num
                            ).first()

                            if not existing:
                                record = Patent(
                                    patent_number=patent_num,
                                    application_number=patent.get("application_number"),
                                    title=patent.get("title"),
                                    abstract=patent.get("abstract"),
                                    grant_date=patent.get("grant_date"),
                                    filing_date=patent.get("filing_date"),
                                    patent_type=patent.get("patent_type"),
                                    claims_count=patent.get("claims_count"),
                                    primary_class=patent.get("primary_class"),
                                    status="granted",
                                )
                                session.add(record)

                                # Create assignee record linking to entity
                                if patent.get("assignee_name"):
                                    assignee = PatentAssignee(
                                        patent_number=patent_num,
                                        assignee_name=patent["assignee_name"],
                                        city=patent.get("assignee_city"),
                                        state=patent.get("assignee_state"),
                                        country=patent.get("assignee_country"),
                                        entity_id=entity["id"],
                                        is_original_assignee=True,
                                    )
                                    session.add(assignee)

                        session.commit()

                    total_patents += len(patents)
                    logger.info(f"  {entity['ticker']}: {len(patents)} patents")

            except Exception as e:
                logger.warning(f"  Error for {entity['name']}: {e}")

    finally:
        await collector.close()

    logger.info(f"USPTO backfill complete: {total_patents} patents")
    return total_patents


async def backfill_air_quality(start_date: date, end_date: date):
    """Backfill OpenAQ air quality data."""
    logger.info(f"Backfilling OpenAQ from {start_date} to {end_date}")
    
    collector = _get_openaq_collector()
    
    # Key cities to monitor
    CITIES = [
        ("US", "Los Angeles"),
        ("US", "Houston"),
        ("US", "Chicago"),
        ("CN", "Beijing"),
        ("CN", "Shanghai"),
        ("CN", "Shenzhen"),
        ("DE", "Frankfurt"),
        ("JP", "Tokyo"),
    ]
    
    PARAMETERS = ["pm25", "pm10", "no2", "o3"]
    
    total_readings = 0
    
    for country, city in CITIES:
        for param in PARAMETERS:
            try:
                readings = await collector.fetch_measurements(
                    country=country,
                    city=city,
                    parameter=param,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Store to database
                with get_db_session() as session:
                    for reading in readings:
                        from src.models.air_quality import AirQualityReading
                        
                        record = AirQualityReading(
                            location_id=reading.get("locationId"),
                            location_name=reading.get("location"),
                            city=city,
                            country=country,
                            latitude=reading.get("coordinates", {}).get("latitude"),
                            longitude=reading.get("coordinates", {}).get("longitude"),
                            parameter=param,
                            value=reading.get("value"),
                            unit=reading.get("unit"),
                            timestamp=reading.get("date", {}).get("utc"),
                        )
                        session.add(record)
                    
                    session.commit()
                
                total_readings += len(readings)
                
            except Exception as e:
                logger.warning(f"  Error for {city}/{param}: {e}")
    
    logger.info(f"OpenAQ backfill complete: {total_readings} readings")
    return total_readings


# ===========================================
# FACTOR COMPUTATION
# ===========================================

async def compute_all_factors(start_date: date, end_date: date):
    """Compute all factors for date range."""
    logger.info(f"Computing factors from {start_date} to {end_date}")

    from src.transformations.base import FactorRegistry

    # Import factor modules to trigger @FactorRegistry.register decorators
    import src.transformations.factors.sec_factors  # noqa: F401
    import src.transformations.factors.macro_factors  # noqa: F401
    import src.transformations.factors.air_quality_factors  # noqa: F401
    import src.transformations.factors.aviation_factors  # noqa: F401
    import src.transformations.factors.power_grid_factors  # noqa: F401
    import src.transformations.factors.patent_factors  # noqa: F401

    # Get all registered factors
    all_factors = FactorRegistry.get_all()

    if not all_factors:
        logger.warning("No factors registered in FactorRegistry")
        return 0

    logger.info(f"  Found {len(all_factors)} registered factors")

    # Get entities - extract values to avoid DetachedInstanceError
    with get_db_session() as session:
        entities_query = session.query(Entity).filter(
            Entity.is_active == True
        ).all()
        entities = [
            {"id": e.id, "entity_type": e.entity_type, "ticker": e.ticker}
            for e in entities_query
        ]

    total_computed = 0

    current = start_date
    while current <= end_date:
        current_dt = datetime.combine(current, datetime.min.time())

        for entity in entities:
            for factor_name, factor_class in all_factors.items():
                # Get factor metadata
                factor_instance = factor_class()
                factor_entity_type = getattr(factor_instance, 'ENTITY_TYPE', 'company')

                # Skip if entity type doesn't match (unless factor is market-level)
                if factor_entity_type != "market" and factor_entity_type != entity["entity_type"]:
                    continue

                try:
                    with get_db_session() as session:
                        # Check if already computed
                        existing = session.query(Factor).filter(
                            Factor.factor_name == factor_name,
                            Factor.entity_id == entity["id"],
                            Factor.effective_date == current_dt
                        ).first()

                        if not existing:
                            # Compute the factor
                            value = factor_instance.compute(
                                entity_id=entity["id"],
                                as_of_date=current_dt
                            )

                            if value is not None:
                                factor = Factor(
                                    factor_name=factor_name,
                                    entity_id=entity["id"],
                                    entity_type=entity["entity_type"],
                                    value=value,
                                    effective_date=current_dt,
                                    computed_at=datetime.utcnow(),
                                    version=1
                                )
                                session.add(factor)
                                session.commit()
                                total_computed += 1

                except Exception as e:
                    logger.debug(f"  Could not compute {factor_name} for {entity['id']} on {current}: {e}")

        current += timedelta(days=1)

        # Progress update
        if (current - start_date).days % 7 == 0:
            logger.info(f"  Progress: {current} ({total_computed} factors computed)")

    logger.info(f"Factor computation complete: {total_computed} factors")
    return total_computed


# ===========================================
# MAIN
# ===========================================

async def main():
    parser = argparse.ArgumentParser(description="Backfill historical data")
    parser.add_argument(
        "--source",
        type=str,
        default="all",
        help="Data source to backfill (sec_edgar, fred, power_grid, patents, air_quality, all)"
    )
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--factors-only",
        action="store_true",
        help="Only compute factors (skip data collection)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without executing"
    )
    
    args = parser.parse_args()
    
    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    
    logger.info("=" * 60)
    logger.info("ALTERNATIVE DATA PLATFORM - BACKFILL")
    logger.info("=" * 60)
    logger.info(f"Source: {args.source}")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Days to process: {(end_date - start_date).days + 1}")
    logger.info("=" * 60)
    
    if args.dry_run:
        logger.info("DRY RUN - No data will be modified")
        return
    
    if not args.factors_only:
        # Backfill data sources
        if args.source in ["all", "sec_edgar"]:
            await backfill_sec_edgar(start_date, end_date)
        
        if args.source in ["all", "fred"]:
            await backfill_fred(start_date, end_date)
        
        if args.source in ["all", "power_grid"]:
            await backfill_power_grid(start_date, end_date)
        
        if args.source in ["all", "patents"]:
            await backfill_patents(start_date, end_date)
        
        if args.source in ["all", "air_quality"]:
            await backfill_air_quality(start_date, end_date)
    
    # Always compute factors at the end
    await compute_all_factors(start_date, end_date)
    
    logger.info("=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

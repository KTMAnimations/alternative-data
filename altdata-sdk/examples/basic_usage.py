"""Basic usage example for the AltData SDK."""

from datetime import date, timedelta

from altdata import AltDataClient


def main():
    # Initialize client - for production, use your API key
    client = AltDataClient(
        api_key="your-api-key",  # Replace with your actual API key
        base_url="http://localhost:8000",  # Or your production URL
    )

    # Check API health
    print("=== Health Check ===")
    health = client.health()
    print(f"Status: {health.status}")
    print(f"Database: {health.database}")
    print(f"Redis: {health.redis}")
    print()

    # List available factors
    print("=== Available Factors ===")
    factors = client.list_factors()
    print(f"Total factors: {factors.total}")
    for factor in factors.factors[:5]:  # Show first 5
        print(f"  - {factor.name} ({factor.category})")
    print()

    # List factors by category
    print("=== SEC Factors ===")
    sec_factors = client.list_factors(category="sec")
    for factor in sec_factors.factors:
        print(f"  - {factor.name}: {factor.description}")
    print()

    # Get factor values for an entity
    print("=== Factor Values for AAPL ===")
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    try:
        data = client.get_factor(
            "insider_transaction_momentum",
            entity_id="AAPL",
            start_date=start_date,
            end_date=end_date,
        )
        print(f"Factor: {data.factor_name}")
        print(f"Entity: {data.entity_id}")
        print(f"Values: {len(data.values)}")

        # Convert to pandas DataFrame
        df = data.to_dataframe()
        print(df.head())
    except Exception as e:
        print(f"Error getting factor: {e}")
    print()

    # Search entities
    print("=== Search Entities ===")
    entities = client.list_entities(search="Apple", page=1, page_size=10)
    print(f"Found {entities.total} entities")
    for entity in entities.entities:
        print(f"  - {entity.name} ({entity.ticker})")
    print()

    # Get entity details
    print("=== Entity Details ===")
    try:
        entity = client.get_entity("AAPL")
        print(f"Name: {entity.name}")
        print(f"Ticker: {entity.ticker}")
        print(f"Type: {entity.entity_type}")
        print(f"Sector: {entity.sector}")
    except Exception as e:
        print(f"Error getting entity: {e}")
    print()

    # List data sources
    print("=== Data Sources ===")
    sources = client.list_sources()
    for source in sources.sources:
        print(f"  - {source.name}: {source.status} ({source.update_frequency})")
    print()

    # Clean up
    client.close()
    print("Done!")


if __name__ == "__main__":
    main()

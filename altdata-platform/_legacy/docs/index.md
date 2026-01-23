# Alternative Data Platform

Welcome to the Alternative Data Platform documentation. This platform aggregates free alternative data sources and computes quantitative factors for backtesting trading strategies.

## Overview

The Alternative Data Platform provides:

- **12+ Data Sources**: SEC EDGAR, FRED, ADS-B flight tracking, power grid data, USPTO patents, OpenAQ air quality, weather, Google Trends, Reddit sentiment, shipping data, GitHub activity, and satellite imagery
- **80+ Quantitative Factors**: Pre-computed factors ready for backtesting
- **REST API**: Easy-to-use JSON API with comprehensive endpoints
- **Python SDK**: pip-installable client library with pandas integration
- **Point-in-Time Accuracy**: All data is timestamped to prevent look-ahead bias

## Quick Start

### Using the API

```bash
# Check health
curl http://localhost:8000/health

# List available factors
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/factors

# Get factor values
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8000/api/v1/factors/insider_transaction_momentum?entity_id=AAPL"
```

### Using the Python SDK

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# List factors
factors = client.list_factors(category="sec")

# Get factor data as pandas DataFrame
data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    start_date="2024-01-01"
)
df = data.to_dataframe()
```

## Data Sources

| Source | Description | Update Frequency |
|--------|-------------|------------------|
| SEC EDGAR | Insider transactions, 13F filings | Real-time |
| FRED | Economic indicators | Daily |
| ADS-B Exchange | Corporate jet tracking | Hourly |
| EIA/ISO | Power grid load data | Hourly |
| USPTO | Patent filings | Weekly |
| OpenAQ | Air quality measurements | Hourly |
| Open-Meteo | Weather data | Hourly |
| Google Trends | Search interest | Daily |
| Reddit | Social sentiment | Hourly |
| MarineTraffic | Port congestion | Daily |
| GitHub | Repository activity | Daily |
| Sentinel Hub | Satellite imagery | Weekly |

## Factor Categories

- **SEC**: Insider transactions, institutional holdings, filing patterns
- **Macro**: Yield curves, economic indicators, credit spreads
- **Aviation**: Corporate jet activity, flight patterns
- **Energy**: Grid load, demand forecasting
- **Patents**: Innovation metrics, R&D activity
- **Environmental**: Air quality indices
- **Weather**: Temperature anomalies, precipitation
- **Trends**: Search interest, trending topics
- **Sentiment**: Social media sentiment scores
- **Shipping**: Port congestion, vessel tracking
- **GitHub**: Developer activity, repository metrics
- **Satellite**: Parking lot occupancy, agricultural health

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Clients   │────▶│   FastAPI   │────▶│  PostgreSQL │
│  (SDK/API)  │     │   Server    │     │ + TimescaleDB│
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Redis    │
                    │   (Cache)   │
                    └─────────────┘
```

## Next Steps

- [Quickstart Guide](getting-started/quickstart.md) - Get up and running in 5 minutes
- [API Reference](api-reference/overview.md) - Full API documentation
- [Factor Catalog](factors/index.md) - Browse all available factors
- [Python SDK](sdk/installation.md) - Install and use the Python client

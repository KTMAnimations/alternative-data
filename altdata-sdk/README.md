# AltData SDK

Python SDK for the Alternative Data Platform API. Access alternative data factors for quantitative trading and research.

## Installation

```bash
pip install altdata
```

For development:

```bash
pip install altdata[dev]
```

## Quick Start

```python
from altdata import AltDataClient

# Initialize client
client = AltDataClient(api_key='your-api-key', base_url='http://localhost:8000')

# List available factors
factors = client.list_factors(category='sec')
print(f"Found {factors.total} SEC factors")

# Get factor data for a company
data = client.get_factor('insider_transaction_momentum', entity_id='AAPL')

# Convert to pandas DataFrame
df = data.to_dataframe()
print(df.head())
```

## Features

- Full coverage of Alternative Data Platform API endpoints
- Type hints throughout
- Pydantic models for all responses
- Built-in DataFrame conversion for data analysis
- Comprehensive error handling with custom exceptions
- Context manager support

## API Reference

### Client Initialization

```python
from altdata import AltDataClient

# Basic initialization
client = AltDataClient(api_key='your-api-key')

# With custom base URL
client = AltDataClient(
    api_key='your-api-key',
    base_url='https://api.yourplatform.com',
    timeout=60.0
)

# Using context manager
with AltDataClient(api_key='your-api-key') as client:
    factors = client.list_factors()
```

### Core Endpoints

#### Health Check

```python
health = client.health()
print(f"Status: {health.status}, Database: {health.database}")
```

#### List Factors

```python
# List all factors
factors = client.list_factors()

# Filter by category
sec_factors = client.list_factors(category='sec')
weather_factors = client.list_factors(category='weather')

# Convert to DataFrame
df = factors.to_dataframe()
```

#### Get Factor Data

```python
from datetime import date

# Get factor values
data = client.get_factor(
    'insider_transaction_momentum',
    entity_id='AAPL',
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31)
)

# Access data
print(f"Factor: {data.factor_name}")
print(f"Entity: {data.entity_id}")
for value in data.values:
    print(f"  {value.date}: {value.value}")

# Convert to DataFrame
df = data.to_dataframe()
```

#### List and Search Entities

```python
# List all entities
entities = client.list_entities()

# Search by name or ticker
entities = client.list_entities(search='Apple')

# Filter by type
companies = client.list_entities(entity_type='company')

# Pagination
page2 = client.list_entities(page=2, page_size=25)
```

#### Get Entity Details

```python
# By ID or ticker
entity = client.get_entity('AAPL')
print(f"{entity.name} ({entity.ticker}) - {entity.sector}")
```

#### List Data Sources

```python
sources = client.list_sources()
for source in sources.sources:
    print(f"{source.name}: {source.status} - {len(source.factors)} factors")
```

### Domain-Specific Endpoints

#### Aviation Data

```python
flights = client.get_flights('AAPL', start_date=date(2024, 1, 1))
df = flights.to_dataframe()
```

#### Energy/Power Grid Data

```python
grid = client.get_grid_load('CAISO', date(2024, 1, 15))
df = grid.to_dataframe()
```

#### Patent Data

```python
patents = client.get_patents('AAPL')
df = patents.to_dataframe()
```

#### Air Quality Data

```python
air_quality = client.get_air_quality(
    date(2024, 1, 15),
    city='Los Angeles',
    parameter='pm25'
)
df = air_quality.to_dataframe()
```

#### Weather Data

```python
# Current observations
weather = client.get_weather('New York', date(2024, 1, 15))

# Forecasts
forecast = client.get_weather_forecast('New York', days=7)
```

#### Google Trends Data

```python
trends = client.get_trends(
    'bitcoin',
    geo='US',
    start_date=date(2024, 1, 1)
)
df = trends.to_dataframe()
```

#### Reddit Sentiment Data

```python
sentiment = client.get_sentiment('AAPL')
df = sentiment.to_dataframe()
```

#### Shipping Data

```python
# List ports
ports = client.list_ports(country='US')

# Get congestion data
congestion = client.get_port_congestion(date(2024, 1, 15), port_id='USLAX')
```

#### GitHub Activity Data

```python
# List repositories
repos = client.list_github_repos(ticker='MSFT')

# Get activity metrics
activity = client.get_github_activity('microsoft/vscode')
df = activity.to_dataframe()
```

#### Satellite Data

```python
# Parking lot occupancy
parking = client.get_parking_data(ticker='WMT')

# Agricultural/NDVI data
agriculture = client.get_agricultural_data('Iowa', crop_type='corn')
```

### Alerts

Create and manage alert rules that trigger notifications when factor values meet specified conditions.

```python
# Create an alert rule
rule = client.create_alert_rule(
    name="AAPL Insider Alert",
    factor_name="insider_transaction_momentum",
    entity_id="AAPL",
    condition="gt",  # greater than
    threshold=1000.0,
    notification_channel="slack",
    notification_config={"webhook_url": "https://hooks.slack.com/..."}
)

# List all alert rules
rules = client.list_alert_rules(is_active=True)
df = rules.to_dataframe()

# Get a specific rule
rule = client.get_alert_rule(rule_id=1)

# Update a rule
updated = client.update_alert_rule(
    rule_id=1,
    threshold=1500.0,
    is_active=False
)

# Delete a rule
client.delete_alert_rule(rule_id=1)

# List triggered notifications
notifications = client.list_alert_notifications(
    rule_id=1,
    status="sent",
    start_date=date(2024, 1, 1)
)

# Manually trigger alert check
result = client.trigger_alert_check()
print(f"Alerts triggered: {result.alerts_triggered}")
```

**Condition Types:**
- `gt` / `lt` / `eq` - Simple threshold comparisons
- `zscore_gt` / `zscore_lt` - Z-score based anomaly detection
- `pct_change_gt` / `pct_change_lt` - Percent change alerts

### Backtesting

Run backtests to evaluate factor performance against historical returns.

```python
from datetime import date

# Run an async backtest (for large universes)
job_id = client.run_backtest(
    factor_name="insider_transaction_momentum",
    universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
    rebalance_freq="weekly",
    long_short=True,
    top_n=10,
    transaction_cost=0.001
)

# Get results (poll until complete)
result = client.get_backtest_result(job_id)
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.1%}")
print(f"IC Mean: {result.ic_mean:.3f}")

# Run a quick synchronous backtest (max 1 year, 50 entities)
result = client.run_backtest_quick(
    factor_name="patent_momentum",
    universe=["AAPL", "MSFT", "GOOGL"],
    start_date=date(2023, 6, 1),
    end_date=date(2023, 12, 31)
)

# Get detailed time series data
timeseries = client.get_backtest_timeseries(job_id)
df = timeseries.to_dataframe()  # cumulative_returns, daily_returns

# Get position history
positions = client.get_backtest_positions(job_id)
df = positions.to_dataframe()  # Position weights per entity

# Get IC (Information Coefficient) series
ic = client.get_backtest_ic(job_id)
df = ic.to_dataframe()

# List recent backtest jobs
jobs = client.list_backtest_jobs(status="complete", limit=10)

# Delete a backtest job
client.delete_backtest_job(job_id)
```

**Backtest Metrics:**
- `sharpe_ratio` - Risk-adjusted return (annualized)
- `sortino_ratio` - Sharpe using downside deviation only
- `max_drawdown` - Largest peak-to-trough decline
- `ic_mean` - Average Information Coefficient
- `ic_ir` - IC consistency (mean/std)
- `turnover` - Average daily position change

## Error Handling

The SDK provides custom exceptions for different error types:

```python
from altdata import (
    AltDataClient,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    ServerError,
    ConnectionError,
)

client = AltDataClient(api_key='your-api-key')

try:
    data = client.get_factor('unknown_factor', entity_id='AAPL')
except AuthenticationError:
    print("Invalid API key")
except NotFoundError as e:
    print(f"Factor not found: {e.message}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except ValidationError:
    print("Invalid request parameters")
except ServerError:
    print("Server error, try again later")
except ConnectionError:
    print("Could not connect to API")
```

## DataFrame Conversion

All list and data responses support `to_dataframe()`:

```python
# Factor data with date index
df = client.get_factor('insider_transaction_momentum', entity_id='AAPL').to_dataframe()

# Entity list
df = client.list_entities(search='tech').to_dataframe()

# Time series data with proper indexing
df = client.get_sentiment('AAPL').to_dataframe()
print(df.index)  # DatetimeIndex
```

## Available Factor Categories

- `sec` - SEC filings (insider transactions, 8-K events)
- `macro` - Macroeconomic indicators (yield curves, credit spreads)
- `aviation` - Corporate jet tracking
- `power_grid` - Electricity demand/generation
- `patents` - USPTO patent filings
- `air_quality` - Environmental monitoring
- `weather` - Weather observations and forecasts
- `trends` - Google Trends data
- `sentiment` - Reddit/social sentiment
- `shipping` - Port congestion and vessel tracking
- `github` - Developer activity metrics
- `satellite` - Satellite imagery analytics

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=altdata --cov-report=html
```

## License

MIT

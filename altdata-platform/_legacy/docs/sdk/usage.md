# SDK Usage

Learn how to use the Alternative Data Platform Python SDK.

## Initialization

### Basic Setup

```python
from altdata import AltDataClient

client = AltDataClient(
    api_key="your-api-key",
    base_url="http://localhost:8000"  # Optional, defaults to localhost
)
```

### Environment Variables

```python
import os
from altdata import AltDataClient

client = AltDataClient(
    api_key=os.environ["ALTDATA_API_KEY"],
    base_url=os.environ.get("ALTDATA_URL", "http://localhost:8000")
)
```

### Context Manager

```python
with AltDataClient(api_key="your-api-key") as client:
    factors = client.list_factors()
    # Client automatically closed when exiting the block
```

### Custom Timeout

```python
client = AltDataClient(
    api_key="your-api-key",
    timeout=60.0  # 60 second timeout
)
```

---

## Core Methods

### Health Check

```python
health = client.health()
print(f"Status: {health.status}")
print(f"Database: {health.database}")
print(f"Redis: {health.redis}")
print(f"Version: {health.version}")
```

### List Factors

```python
# All factors
factors = client.list_factors()
print(f"Total: {factors.total}")

for f in factors.factors:
    print(f"{f.name} ({f.category})")

# Filter by category
sec_factors = client.list_factors(category="sec")
```

### Get Factor Values

```python
from datetime import date

data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    start_date=date(2024, 1, 1),
    end_date=date(2024, 6, 30)
)

print(f"Factor: {data.factor_name}")
print(f"Entity: {data.entity_id}")
print(f"Values: {len(data.values)}")

# Convert to DataFrame
df = data.to_dataframe()
print(df.head())
```

### List Entities

```python
# All entities
entities = client.list_entities()

# Search
results = client.list_entities(search="Apple")

# Filter by type
companies = client.list_entities(entity_type="company")

# Paginate
page2 = client.list_entities(page=2, page_size=25)

# Convert to DataFrame
df = entities.to_dataframe()
```

### Get Entity Details

```python
entity = client.get_entity("AAPL")
print(f"Name: {entity.name}")
print(f"Sector: {entity.sector}")
```

### List Data Sources

```python
sources = client.list_sources()
for s in sources.sources:
    print(f"{s.name}: {s.status}")
```

---

## Data Source Methods

### Aviation

```python
from datetime import date

flights = client.get_flights(
    company_id="AAPL",
    start_date=date(2024, 1, 1)
)
df = flights.to_dataframe()
```

### Energy

```python
load = client.get_grid_load("CAISO", date(2024, 1, 15))
df = load.to_dataframe()
```

### Patents

```python
patents = client.get_patents(company_id="AAPL")
df = patents.to_dataframe()
```

### Environment

```python
aq = client.get_air_quality(
    date(2024, 1, 15),
    city="Los Angeles"
)
df = aq.to_dataframe()
```

### Weather

```python
# Observations
weather = client.get_weather("New York", date(2024, 1, 15))
df = weather.to_dataframe()

# Forecast
forecast = client.get_weather_forecast("New York", days=7)
df = forecast.to_dataframe()
```

### Trends

```python
trends = client.get_trends(
    keyword="bitcoin",
    geo="US",
    start_date=date(2024, 1, 1)
)
df = trends.to_dataframe()
```

### Sentiment

```python
sentiment = client.get_sentiment(
    ticker="AAPL",
    start_date=date(2024, 1, 1)
)
df = sentiment.to_dataframe()
```

### Shipping

```python
# List ports
ports = client.list_ports(country="US")

# Get congestion
congestion = client.get_port_congestion(date(2024, 1, 15))
df = congestion.to_dataframe()
```

### GitHub

```python
# List repos
repos = client.list_github_repos(ticker="MSFT")

# Get activity
activity = client.get_github_activity("microsoft/vscode")
df = activity.to_dataframe()
```

### Satellite

```python
# Parking data
parking = client.get_parking_data(ticker="WMT")
df = parking.to_dataframe()

# Agricultural data
ag = client.get_agricultural_data("Iowa", crop_type="corn")
df = ag.to_dataframe()
```

---

## Error Handling

```python
from altdata import (
    AltDataClient,
    AltDataError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    ServerError,
    ConnectionError,
)

client = AltDataClient(api_key="your-api-key")

try:
    data = client.get_factor("unknown_factor", entity_id="AAPL")
except AuthenticationError:
    print("Invalid API key")
except NotFoundError:
    print("Factor not found")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except ValidationError:
    print("Invalid request parameters")
except ServerError:
    print("Server error - try again later")
except ConnectionError:
    print("Could not connect to API")
except AltDataError as e:
    print(f"API error: {e.message} (status {e.status_code})")
```

---

## Best Practices

### 1. Use Context Managers

```python
with AltDataClient(api_key="key") as client:
    # Client is automatically closed
    data = client.get_factor("factor", entity_id="AAPL")
```

### 2. Cache Responses

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_factor_cached(factor_name, entity_id, start_date):
    return client.get_factor(factor_name, entity_id, start_date=start_date)
```

### 3. Handle Rate Limits

```python
import time

def fetch_with_retry(func, *args, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(e.retry_after or (2 ** attempt))
```

### 4. Close Client When Done

```python
client = AltDataClient(api_key="key")
try:
    # Use client
    data = client.get_factor("factor", entity_id="AAPL")
finally:
    client.close()
```

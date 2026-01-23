# Data Sources API

The Data Sources API provides information about available data sources and their status.

## List Sources

List all available data sources with their status and metadata.

```
GET /api/v1/sources
```

### Response

```json
{
  "sources": [
    {
      "id": "sec_edgar",
      "name": "SEC EDGAR",
      "category": "regulatory",
      "status": "active",
      "update_frequency": "real-time",
      "factors": [
        "insider_transaction_momentum",
        "form4_net_shares",
        "insider_buy_ratio"
      ]
    },
    {
      "id": "fred",
      "name": "Federal Reserve Economic Data",
      "category": "macro",
      "status": "active",
      "update_frequency": "daily",
      "factors": [
        "yield_curve_slope",
        "credit_spread",
        "unemployment_change"
      ]
    }
  ]
}
```

### Example

=== "cURL"
    ```bash
    curl -H "X-API-Key: your-api-key" \
      http://localhost:8000/api/v1/sources
    ```

=== "Python SDK"
    ```python
    from altdata import AltDataClient

    client = AltDataClient(api_key="your-api-key")

    sources = client.list_sources()
    for source in sources.sources:
        status_icon = "🟢" if source.status == "active" else "🔴"
        print(f"{status_icon} {source.name}: {source.update_frequency}")
    ```

---

## Available Data Sources

### Phase 1 Sources

| Source | Category | Update Frequency | Description |
|--------|----------|------------------|-------------|
| SEC EDGAR | regulatory | Real-time | Insider transactions, 13F filings |
| FRED | macro | Daily | Federal Reserve economic indicators |
| ADS-B Exchange | aviation | Hourly | Corporate jet flight tracking |
| EIA/ISO | energy | Hourly | Power grid load data |
| USPTO | patents | Weekly | Patent filings and grants |
| OpenAQ | environment | Hourly | Air quality measurements |

### Phase 2 Sources

| Source | Category | Update Frequency | Description |
|--------|----------|------------------|-------------|
| Open-Meteo | weather | Hourly | Weather observations and forecasts |
| Google Trends | trends | Daily | Search interest data |
| Reddit | sentiment | Hourly | Social media sentiment |
| MarineTraffic | shipping | Daily | Port congestion data |
| GitHub | development | Daily | Repository activity metrics |
| Sentinel Hub | satellite | Weekly | Satellite imagery analysis |

---

## Source Status Values

| Status | Description |
|--------|-------------|
| `active` | Source is fully operational |
| `degraded` | Source has reduced functionality |
| `maintenance` | Source is under maintenance |
| `offline` | Source is unavailable |

---

## Source Response Models

### DataSource

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique source identifier |
| `name` | string | Human-readable name |
| `category` | string | Source category |
| `status` | string | Current status |
| `update_frequency` | string | How often data updates |
| `factors` | array | List of factors from this source |

### SourcesResponse

| Field | Type | Description |
|-------|------|-------------|
| `sources` | array | List of DataSource objects |

---

## Checking Source Health

To monitor data source health:

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")
sources = client.list_sources()

# Check for any degraded or offline sources
for source in sources.sources:
    if source.status != "active":
        print(f"⚠️  {source.name} is {source.status}")
```

---

## Source-Specific Endpoints

Each data source category has specific endpoints for raw data access:

### Aviation

```
GET /api/v1/aviation/flights?company_id=AAPL
```

### Energy

```
GET /api/v1/energy/load?iso=CAISO&date=2024-01-15
```

### Patents

```
GET /api/v1/patents/filings?company_id=AAPL
```

### Environment

```
GET /api/v1/environment/air-quality?city=Los%20Angeles&date=2024-01-15
```

### Weather

```
GET /api/v1/weather/observations?city=New%20York&date=2024-01-15
GET /api/v1/weather/forecast?city=New%20York&days=7
```

### Trends

```
GET /api/v1/trends/interest?keyword=bitcoin&geo=US
```

### Sentiment

```
GET /api/v1/sentiment/ticker?ticker=AAPL
```

### Shipping

```
GET /api/v1/shipping/ports
GET /api/v1/shipping/congestion?date=2024-01-15
```

### GitHub

```
GET /api/v1/github/repos?ticker=MSFT
GET /api/v1/github/activity?repo=microsoft/vscode
```

### Satellite

```
GET /api/v1/satellite/parking?ticker=WMT
GET /api/v1/satellite/agriculture?region=Iowa
```

See the [Python SDK documentation](../sdk/usage.md) for detailed examples of each endpoint.

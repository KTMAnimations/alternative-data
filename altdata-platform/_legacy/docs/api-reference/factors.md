# Factors API

The Factors API provides access to quantitative factors computed from alternative data sources.

## List Factors

List all available factors with optional category filtering.

```
GET /api/v1/factors
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Filter by category (e.g., `sec`, `macro`, `aviation`) |

### Response

```json
{
  "factors": [
    {
      "id": "insider_transaction_momentum",
      "name": "Insider Transaction Momentum",
      "description": "Momentum of insider buying/selling activity",
      "category": "sec",
      "frequency": "daily"
    },
    {
      "id": "yield_curve_slope",
      "name": "Yield Curve Slope",
      "description": "10Y-2Y Treasury spread",
      "category": "macro",
      "frequency": "daily"
    }
  ],
  "total": 80
}
```

### Example

=== "cURL"
    ```bash
    curl -H "X-API-Key: your-api-key" \
      "http://localhost:8000/api/v1/factors?category=sec"
    ```

=== "Python SDK"
    ```python
    from altdata import AltDataClient

    client = AltDataClient(api_key="your-api-key")
    factors = client.list_factors(category="sec")

    for factor in factors.factors:
        print(f"{factor.name}: {factor.description}")
    ```

---

## Get Factor Values

Get factor values for a specific entity over a time range.

```
GET /api/v1/factors/{factor_name}
```

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `factor_name` | string | The factor identifier (e.g., `insider_transaction_momentum`) |

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_id` | string | Yes | Entity identifier (e.g., `AAPL`) |
| `start_date` | date | No | Start date (ISO 8601) |
| `end_date` | date | No | End date (ISO 8601) |

### Response

```json
{
  "factor_name": "insider_transaction_momentum",
  "entity_id": "AAPL",
  "entity_type": "company",
  "values": [
    {
      "date": "2024-01-15T00:00:00",
      "value": 0.75,
      "version": 1
    },
    {
      "date": "2024-01-14T00:00:00",
      "value": 0.68,
      "version": 1
    }
  ],
  "metadata": {
    "computed_at": "2024-01-15T10:30:00"
  }
}
```

### Example

=== "cURL"
    ```bash
    curl -H "X-API-Key: your-api-key" \
      "http://localhost:8000/api/v1/factors/insider_transaction_momentum?entity_id=AAPL&start_date=2024-01-01&end_date=2024-06-30"
    ```

=== "Python SDK"
    ```python
    from altdata import AltDataClient
    from datetime import date

    client = AltDataClient(api_key="your-api-key")

    data = client.get_factor(
        "insider_transaction_momentum",
        entity_id="AAPL",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 6, 30)
    )

    # Convert to pandas DataFrame
    df = data.to_dataframe()
    print(df.head())
    ```

---

## List Categories

List all factor categories.

```
GET /api/v1/categories
```

### Response

```json
{
  "categories": [
    {
      "id": "sec",
      "name": "SEC",
      "count": 15,
      "factors": ["insider_transaction_momentum", "form4_net_shares", ...]
    },
    {
      "id": "macro",
      "name": "Macro",
      "count": 10,
      "factors": ["yield_curve_slope", "credit_spread", ...]
    }
  ]
}
```

### Example

=== "cURL"
    ```bash
    curl -H "X-API-Key: your-api-key" \
      http://localhost:8000/api/v1/categories
    ```

=== "Python SDK"
    ```python
    from altdata import AltDataClient

    client = AltDataClient(api_key="your-api-key")
    categories = client.list_categories()

    for cat in categories.categories:
        print(f"{cat.name}: {cat.count} factors")
    ```

---

## Factor Response Models

### FactorListItem

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique factor identifier |
| `name` | string | Human-readable name |
| `description` | string | Factor description |
| `category` | string | Factor category |
| `frequency` | string | Update frequency (daily, weekly, etc.) |

### FactorValue

| Field | Type | Description |
|-------|------|-------------|
| `date` | datetime | Point-in-time date |
| `value` | float | Factor value |
| `version` | int | Factor version |

### FactorResponse

| Field | Type | Description |
|-------|------|-------------|
| `factor_name` | string | Factor identifier |
| `entity_id` | string | Entity identifier |
| `entity_type` | string | Entity type |
| `values` | array | List of FactorValue objects |
| `metadata` | object | Additional metadata |

---

## Error Responses

### Factor Not Found

```json
{
  "detail": "Factor not found: unknown_factor"
}
```

HTTP Status: `404 Not Found`

### Missing Entity ID

```json
{
  "detail": "entity_id is required"
}
```

HTTP Status: `422 Validation Error`

### No Data Available

```json
{
  "factor_name": "insider_transaction_momentum",
  "entity_id": "UNKNOWN",
  "entity_type": "company",
  "values": [],
  "metadata": {}
}
```

When no data is available for an entity, the response returns an empty values array with HTTP Status `200 OK`.

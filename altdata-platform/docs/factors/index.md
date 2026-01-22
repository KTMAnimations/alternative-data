# Factor Catalog

The Alternative Data Platform provides 80+ quantitative factors across 12 categories. Factors are computed from alternative data sources and designed for backtesting trading strategies.

## Overview

All factors share common properties:

- **Point-in-Time Accuracy**: Values are timestamped to prevent look-ahead bias
- **Daily Updates**: Most factors update daily (some more frequently)
- **API Access**: Available via REST API and Python SDK
- **DataFrame Export**: Convert to pandas DataFrames for analysis

## Factor Categories

| Category | Factors | Description |
|----------|---------|-------------|
| [SEC](sec.md) | 15+ | Insider transactions, institutional holdings |
| [Macro](macro.md) | 10+ | Yield curves, economic indicators |
| [Aviation](aviation.md) | 5+ | Corporate jet activity |
| [Energy](energy.md) | 8+ | Power grid load and demand |
| [Patents](patents.md) | 6+ | Innovation and R&D metrics |
| [Environmental](environmental.md) | 5+ | Air quality indices |
| [Weather](weather.md) | 8+ | Temperature, precipitation anomalies |
| [Trends](trends.md) | 5+ | Search interest metrics |
| [Sentiment](sentiment.md) | 8+ | Social media sentiment |
| [Shipping](shipping.md) | 6+ | Port congestion metrics |
| [GitHub](github.md) | 7+ | Developer activity |
| [Satellite](satellite.md) | 5+ | Parking lot occupancy, agriculture |

## Using Factors

### List All Factors

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")
factors = client.list_factors()

for f in factors.factors:
    print(f"{f.name} ({f.category}): {f.description}")
```

### Get Factor Values

```python
data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    start_date="2024-01-01",
    end_date="2024-06-30"
)

df = data.to_dataframe()
print(df.head())
```

### Filter by Category

```python
sec_factors = client.list_factors(category="sec")
macro_factors = client.list_factors(category="macro")
```

## Factor Properties

Each factor has the following properties:

| Property | Description |
|----------|-------------|
| `id` | Unique identifier (e.g., `insider_transaction_momentum`) |
| `name` | Human-readable name |
| `description` | What the factor measures |
| `category` | Factor category |
| `entity_type` | What entities it applies to (company, region, market) |
| `frequency` | Update frequency (daily, weekly, etc.) |

## Factor Value Structure

Factor values include:

| Field | Type | Description |
|-------|------|-------------|
| `date` | datetime | Point-in-time date |
| `value` | float | Factor value |
| `version` | int | Factor version (for schema changes) |

## Best Practices

### 1. Avoid Look-Ahead Bias

Always use point-in-time factor values:

```python
# Correct: Use as-of-date
data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    end_date="2024-01-15"  # Only data available as of this date
)
```

### 2. Handle Missing Data

Some factors may have gaps:

```python
df = data.to_dataframe()
df = df.ffill()  # Forward fill missing values
```

### 3. Normalize for Cross-Sectional Analysis

When comparing across entities:

```python
# Z-score normalization within each date
df_pivot = df.pivot(columns='ticker', values='value')
df_zscore = (df_pivot - df_pivot.mean(axis=1)) / df_pivot.std(axis=1)
```

### 4. Combine Multiple Factors

Create composite signals:

```python
factors = ["insider_transaction_momentum", "sentiment_score", "patent_momentum"]

dfs = []
for factor in factors:
    data = client.get_factor(factor, entity_id="AAPL")
    df = data.to_dataframe()
    df.columns = [factor]
    dfs.append(df)

combined = pd.concat(dfs, axis=1)
combined['composite'] = combined.mean(axis=1)
```

## Factor Updates

Factors are updated on the following schedule:

| Source | Update Time | Frequency |
|--------|-------------|-----------|
| SEC EDGAR | 6:00 AM ET | Real-time |
| FRED | 8:30 AM ET | Daily |
| Weather | Hourly | Hourly |
| Trends | 2:00 AM ET | Daily |
| Sentiment | Hourly | Hourly |
| GitHub | 3:00 AM ET | Daily |
| Satellite | Weekly | Weekly |

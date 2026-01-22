# SDK Examples

Code examples for common use cases with the Alternative Data Platform SDK.

## Basic Examples

### Fetch Factor Data

```python
from altdata import AltDataClient
from datetime import date

client = AltDataClient(api_key="your-api-key")

# Get insider transaction momentum for Apple
data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    start_date=date(2024, 1, 1),
    end_date=date(2024, 6, 30)
)

# Convert to pandas DataFrame
df = data.to_dataframe()
print(df.head())

client.close()
```

### Search for Entities

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Search for tech companies
results = client.list_entities(search="tech", entity_type="company")

for entity in results.entities:
    print(f"{entity.name} ({entity.ticker})")

client.close()
```

---

## Analysis Examples

### Factor Screening

Screen multiple tickers for a factor signal:

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"]

signals = {}
for ticker in tickers:
    try:
        data = client.get_factor(
            "insider_transaction_momentum",
            entity_id=ticker
        )
        if data.values:
            signals[ticker] = data.values[0].value
    except Exception as e:
        print(f"Error for {ticker}: {e}")

# Sort by signal strength
sorted_signals = sorted(signals.items(), key=lambda x: x[1], reverse=True)

print("Insider Buying Signal Ranking:")
for ticker, value in sorted_signals:
    direction = "BUY" if value > 0 else "SELL"
    print(f"  {ticker}: ${value:,.0f} ({direction})")

client.close()
```

### Multi-Factor Analysis

Combine multiple factors for a composite signal:

```python
from altdata import AltDataClient
import pandas as pd

client = AltDataClient(api_key="your-api-key")

ticker = "AAPL"
factors = [
    "insider_transaction_momentum",
    "sentiment_score",
    "patent_filing_momentum"
]

# Fetch all factors
factor_data = {}
for factor in factors:
    try:
        data = client.get_factor(factor, entity_id=ticker)
        factor_data[factor] = data.to_dataframe()["value"]
    except Exception as e:
        print(f"Error for {factor}: {e}")

# Combine into single DataFrame
combined = pd.DataFrame(factor_data)

# Z-score normalize
normalized = (combined - combined.mean()) / combined.std()

# Create composite score
combined["composite"] = normalized.mean(axis=1)

print(combined.tail())

client.close()
```

### Time Series Correlation

Analyze correlation between factor and returns:

```python
from altdata import AltDataClient
import pandas as pd
import yfinance as yf

client = AltDataClient(api_key="your-api-key")

# Get factor data
factor_data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    start_date="2023-01-01"
)
factor_df = factor_data.to_dataframe()

# Get price data
prices = yf.download("AAPL", start="2023-01-01")["Adj Close"]
returns = prices.pct_change()

# Calculate forward returns (next 20 days)
forward_returns = returns.shift(-20).rolling(20).sum()

# Merge
merged = factor_df.join(forward_returns.rename("fwd_return"), how="inner")

# Calculate correlation
correlation = merged["value"].corr(merged["fwd_return"])
print(f"Factor → 20-day Forward Return Correlation: {correlation:.3f}")

client.close()
```

---

## Portfolio Examples

### Factor-Based Ranking

Rank a universe of stocks by factor value:

```python
from altdata import AltDataClient
import pandas as pd

client = AltDataClient(api_key="your-api-key")

# Define universe
universe = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA",
            "TSLA", "JPM", "V", "WMT", "PG", "JNJ"]

# Fetch factor for all tickers
factor_values = []
for ticker in universe:
    try:
        data = client.get_factor(
            "insider_transaction_momentum",
            entity_id=ticker
        )
        if data.values:
            factor_values.append({
                "ticker": ticker,
                "factor_value": data.values[0].value
            })
    except Exception:
        pass

# Create DataFrame and rank
df = pd.DataFrame(factor_values)
df["rank"] = df["factor_value"].rank(ascending=False)
df = df.sort_values("rank")

print("Factor Ranking:")
print(df.to_string(index=False))

# Top 3 for long, bottom 3 for short
long_tickers = df.head(3)["ticker"].tolist()
short_tickers = df.tail(3)["ticker"].tolist()

print(f"\nLong: {long_tickers}")
print(f"Short: {short_tickers}")

client.close()
```

---

## Monitoring Examples

### Check Data Source Status

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

sources = client.list_sources()

print("Data Source Status:")
for source in sources.sources:
    status_icon = {
        "active": "🟢",
        "degraded": "🟡",
        "offline": "🔴"
    }.get(source.status, "⚪")

    print(f"{status_icon} {source.name}: {source.status} ({source.update_frequency})")

client.close()
```

### Monitor Factor Changes

```python
from altdata import AltDataClient
from datetime import date, timedelta

client = AltDataClient(api_key="your-api-key")

ticker = "AAPL"
factor = "insider_transaction_momentum"

# Get recent data
data = client.get_factor(
    factor,
    entity_id=ticker,
    start_date=date.today() - timedelta(days=7)
)

if len(data.values) >= 2:
    current = data.values[0].value
    previous = data.values[1].value
    change = current - previous

    print(f"{ticker} {factor}:")
    print(f"  Current: {current:,.0f}")
    print(f"  Previous: {previous:,.0f}")
    print(f"  Change: {change:+,.0f}")

    if abs(change) > abs(previous) * 0.5:
        print("  ⚠️ Large change detected!")

client.close()
```

---

## Batch Processing

### Fetch Multiple Factors Efficiently

```python
from altdata import AltDataClient
from concurrent.futures import ThreadPoolExecutor
import time

def fetch_factor_safe(args):
    """Fetch a single factor with rate limiting."""
    client, factor, ticker = args
    try:
        data = client.get_factor(factor, entity_id=ticker)
        return (factor, ticker, data.values[0].value if data.values else None)
    except Exception as e:
        return (factor, ticker, None)

client = AltDataClient(api_key="your-api-key")

factors = ["insider_transaction_momentum", "sentiment_score"]
tickers = ["AAPL", "MSFT", "GOOGL"]

# Create all combinations
tasks = [(client, f, t) for f in factors for t in tickers]

# Fetch with delay to respect rate limits
results = []
for task in tasks:
    result = fetch_factor_safe(task)
    results.append(result)
    time.sleep(0.1)  # Small delay

# Process results
for factor, ticker, value in results:
    if value is not None:
        print(f"{ticker} {factor}: {value}")

client.close()
```

---

## Export Examples

### Export to CSV

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    start_date="2024-01-01"
)

df = data.to_dataframe()
df.to_csv("aapl_insider_momentum.csv")

print(f"Exported {len(df)} rows to aapl_insider_momentum.csv")

client.close()
```

### Export Entity List

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Fetch all entities
all_entities = []
page = 1

while True:
    result = client.list_entities(page=page, page_size=100)
    all_entities.extend(result.entities)

    if len(all_entities) >= result.total:
        break
    page += 1

# Convert to DataFrame and export
import pandas as pd
df = pd.DataFrame([e.model_dump() for e in all_entities])
df.to_csv("entities.csv", index=False)

print(f"Exported {len(df)} entities to entities.csv")

client.close()
```

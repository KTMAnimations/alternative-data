# Rate Limits

The Alternative Data Platform implements rate limiting to ensure fair usage and system stability.

## Rate Limit Tiers

| Tier | Requests/Minute | Requests/Day |
|------|-----------------|--------------|
| Free | 60 | 1,000 |
| Standard | 300 | 10,000 |
| Premium | 1,000 | 100,000 |

## Rate Limit Headers

All API responses include rate limit information in the headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed |
| `X-RateLimit-Remaining` | Requests remaining in window |
| `X-RateLimit-Reset` | Unix timestamp when limit resets |

Example response headers:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705320000
```

## Rate Limit Exceeded

When you exceed the rate limit, the API returns:

- HTTP Status: `429 Too Many Requests`
- `Retry-After` header with seconds to wait

```json
{
  "detail": "Rate limit exceeded. Please retry after 60 seconds."
}
```

## SDK Handling

The Python SDK provides a specific exception for rate limits:

```python
from altdata import AltDataClient, RateLimitError
import time

client = AltDataClient(api_key="your-api-key")

try:
    factors = client.list_factors()
except RateLimitError as e:
    print(f"Rate limit exceeded. Retry after {e.retry_after} seconds")
    time.sleep(e.retry_after)
    # Retry the request
    factors = client.list_factors()
```

## Best Practices

### 1. Implement Exponential Backoff

```python
import time
from altdata import AltDataClient, RateLimitError

def fetch_with_retry(client, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.list_factors()
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            wait_time = e.retry_after or (2 ** attempt)
            print(f"Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)
```

### 2. Cache Responses

Factor values don't change frequently. Cache responses to reduce API calls:

```python
from functools import lru_cache
from datetime import date

@lru_cache(maxsize=100)
def get_cached_factor(client, factor_name, entity_id, start_date):
    return client.get_factor(factor_name, entity_id, start_date=start_date)
```

### 3. Batch Requests

When fetching data for multiple entities, batch your requests:

```python
from concurrent.futures import ThreadPoolExecutor
import time

def fetch_multiple_entities(client, factor_name, entity_ids):
    results = {}

    for entity_id in entity_ids:
        results[entity_id] = client.get_factor(factor_name, entity_id)
        time.sleep(0.1)  # Small delay to avoid rate limits

    return results
```

### 4. Use Webhooks (Coming Soon)

For real-time updates, webhooks avoid polling:

```python
# Instead of polling:
while True:
    data = client.get_factor("my_factor", "AAPL")
    time.sleep(60)

# Use webhooks (coming soon):
# client.subscribe_webhook("my_factor", "AAPL", callback_url)
```

## Per-Endpoint Limits

Some endpoints have specific rate limits:

| Endpoint | Limit |
|----------|-------|
| `GET /api/v1/factors` | Standard |
| `GET /api/v1/factors/{name}` | Standard |
| `POST /api/v1/backtest/run` | 10/hour |
| `GET /api/v1/satellite/*` | 30/minute |

## Monitoring Usage

Check your current usage:

```bash
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/usage
```

Response:

```json
{
  "requests_today": 450,
  "requests_limit": 1000,
  "rate_limit": 60,
  "rate_remaining": 45
}
```

# Quickstart

Get up and running with the Alternative Data Platform in 5 minutes.

## Prerequisites

- Python 3.9+
- Docker and Docker Compose (for self-hosting)
- An API key (for production access)

## Option 1: Using the Python SDK

The easiest way to get started is with the Python SDK.

### Installation

```bash
pip install altdata
```

### Basic Usage

```python
from altdata import AltDataClient

# Initialize client
client = AltDataClient(
    api_key="your-api-key",
    base_url="http://localhost:8000"  # Or production URL
)

# Check API health
health = client.health()
print(f"Status: {health.status}")

# List available factors
factors = client.list_factors()
print(f"Available factors: {factors.total}")

# Get factor data for a company
data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    start_date="2024-01-01",
    end_date="2024-06-30"
)

# Convert to pandas DataFrame
df = data.to_dataframe()
print(df.head())
```

## Option 2: Using the REST API

### Check Health

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0"
}
```

### List Factors

```bash
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/factors
```

### Get Factor Values

```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8000/api/v1/factors/insider_transaction_momentum?entity_id=AAPL&start_date=2024-01-01"
```

## Option 3: Self-Hosting

### 1. Clone the Repository

```bash
git clone https://github.com/KTMAnimations/alternative-data.git
cd alternative-data/altdata-platform
```

### 2. Start Services

```bash
docker-compose up -d db redis
```

### 3. Set Up Python Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Initialize Database

```bash
python scripts/init_db.py
```

### 5. Start the API

```bash
uvicorn src.api.main:app --reload --port 8000
```

### 6. Verify

```bash
curl http://localhost:8000/health
```

## Next Steps

- [Authentication](authentication.md) - Learn about API authentication
- [Rate Limits](rate-limits.md) - Understand rate limiting
- [Factor Catalog](../factors/index.md) - Browse available factors
- [API Reference](../api-reference/overview.md) - Full API documentation

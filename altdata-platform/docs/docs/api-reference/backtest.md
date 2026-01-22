# Backtest API

The Backtest API allows you to evaluate factor performance against historical returns using quantitative metrics.

## Overview

Run backtests to measure how well a factor predicts future returns. The framework supports:

- **Long-short strategies**: Go long top-ranked, short bottom-ranked
- **Long-only strategies**: Only take long positions
- **Multiple rebalance frequencies**: Daily, weekly, monthly
- **Comprehensive metrics**: Sharpe, Sortino, IC, drawdown, turnover

---

## Endpoints

### Run Backtest (Async)

Submit a backtest job for asynchronous execution. Use this for large backtests.

```
POST /api/v1/backtest/run
```

**Request Body:**

```json
{
  "factor_name": "insider_transaction_momentum",
  "universe": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "rebalance_freq": "weekly",
  "long_short": true,
  "top_n": 10,
  "transaction_cost": 0.001
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `factor_name` | string | Yes | Factor to backtest |
| `universe` | array | Yes | List of entity IDs (2-500) |
| `start_date` | date | Yes | Backtest start date |
| `end_date` | date | Yes | Backtest end date |
| `rebalance_freq` | string | No | `daily`, `weekly`, `monthly` (default: daily) |
| `long_short` | boolean | No | Long-short or long-only (default: true) |
| `top_n` | int | No | Positions per side (default: 10) |
| `transaction_cost` | float | No | Cost per trade as fraction (default: 0.001) |

**Response:** `202 Accepted`

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "running"
}
```

---

### Run Backtest (Quick)

Run a small backtest synchronously and get results immediately.

```
POST /api/v1/backtest/quick
```

**Limitations:**
- Maximum date range: 1 year
- Maximum universe size: 50 entities

**Request Body:** Same as `/run`

**Response:** `200 OK`

Returns full backtest metrics immediately (see Get Results below).

---

### Get Backtest Results

Get the results of a backtest job.

```
GET /api/v1/backtest/results/{job_id}
```

**Response:** `200 OK`

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "complete",
  "factor_name": "insider_transaction_momentum",
  "universe_size": 7,
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "rebalance_freq": "weekly",
  "long_short": true,
  "top_n": 10,
  "sharpe_ratio": 1.45,
  "sortino_ratio": 2.12,
  "calmar_ratio": 1.89,
  "max_drawdown": -0.12,
  "total_return": 0.23,
  "annualized_return": 0.25,
  "volatility": 0.15,
  "ic_mean": 0.05,
  "ic_ir": 1.2,
  "win_rate": 0.55,
  "profit_factor": 1.8,
  "turnover": 0.2,
  "completed_at": "2024-01-15T10:35:00Z"
}
```

**Status Values:**

| Status | Description |
|--------|-------------|
| `running` | Backtest is still processing |
| `complete` | Backtest finished successfully |
| `failed` | Backtest failed (check `error` field) |

---

### Get Time Series

Get the returns time series for a completed backtest.

```
GET /api/v1/backtest/results/{job_id}/timeseries
```

**Response:** `200 OK`

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "dates": ["2023-01-03", "2023-01-04", "2023-01-05"],
  "cumulative_returns": [1.0, 1.002, 1.005],
  "daily_returns": [0.0, 0.002, 0.003]
}
```

---

### Get Positions

Get the position history for a completed backtest.

```
GET /api/v1/backtest/results/{job_id}/positions
```

**Response:** `200 OK`

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "dates": ["2023-01-03", "2023-01-10", "2023-01-17"],
  "positions": {
    "AAPL": [0.1, 0.1, 0.0],
    "MSFT": [0.1, 0.0, 0.1],
    "GOOGL": [-0.1, -0.1, -0.1]
  }
}
```

Positive values indicate long positions, negative values indicate short positions.

---

### Get IC Series

Get the Information Coefficient time series.

```
GET /api/v1/backtest/results/{job_id}/ic
```

**Response:** `200 OK`

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "dates": ["2023-01-03", "2023-01-04", "2023-01-05"],
  "ic_values": [0.05, 0.03, 0.07],
  "ic_mean": 0.05,
  "ic_ir": 1.2
}
```

---

### List Jobs

List recent backtest jobs.

```
GET /api/v1/backtest/jobs
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `running`, `complete`, `failed` |
| `limit` | int | Max results (default: 50, max: 100) |

**Response:** `200 OK`

```json
{
  "jobs": [
    {
      "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "status": "complete",
      "factor_name": "insider_transaction_momentum",
      "submitted_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

---

### Delete Job

Delete a backtest job and its results.

```
DELETE /api/v1/backtest/jobs/{job_id}
```

**Response:** `204 No Content`

---

## Metrics Explained

### Performance Metrics

| Metric | Description | Good Value |
|--------|-------------|------------|
| `sharpe_ratio` | Risk-adjusted return (annualized) | > 1.0 |
| `sortino_ratio` | Sharpe using downside deviation only | > 1.5 |
| `calmar_ratio` | Return / max drawdown | > 1.0 |
| `max_drawdown` | Largest peak-to-trough decline | > -0.20 |
| `total_return` | Cumulative return over period | Positive |
| `annualized_return` | Yearly return rate | > 0.10 |
| `volatility` | Annualized standard deviation | < 0.20 |

### Factor Quality Metrics

| Metric | Description | Good Value |
|--------|-------------|------------|
| `ic_mean` | Average Information Coefficient | > 0.03 |
| `ic_ir` | IC mean / IC std (consistency) | > 0.5 |
| `turnover` | Average daily position change | < 0.5 |

### Trade Metrics

| Metric | Description | Good Value |
|--------|-------------|------------|
| `win_rate` | Percentage of positive days | > 0.50 |
| `profit_factor` | Gross profit / gross loss | > 1.5 |

---

## Examples

### Basic Backtest

```bash
curl -X POST "https://api.altdata.example.com/api/v1/backtest/run" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "factor_name": "insider_transaction_momentum",
    "universe": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "rebalance_freq": "weekly",
    "long_short": true,
    "top_n": 2
  }'
```

### Check Results

```bash
curl "https://api.altdata.example.com/api/v1/backtest/results/a1b2c3d4..." \
  -H "X-API-Key: your-api-key"
```

### Python SDK Example

```python
from altdata import AltDataClient
from datetime import date

client = AltDataClient(api_key="your-api-key")

# Run backtest
job_id = client.run_backtest(
    factor_name="insider_transaction_momentum",
    universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
    rebalance_freq="weekly",
    long_short=True,
    top_n=2
)

# Wait for completion and get results
result = client.get_backtest_result(job_id)

print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.1%}")
print(f"IC Mean: {result.ic_mean:.3f}")

# Get returns as DataFrame
returns_df = result.to_dataframe()
```

### Long-Only Strategy

```python
# Long-only backtest (no shorting)
job_id = client.run_backtest(
    factor_name="patent_momentum",
    universe=tech_stocks,
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
    long_short=False,  # Long only
    top_n=10
)
```

### Monthly Rebalancing

```python
# Rebalance monthly to reduce turnover
job_id = client.run_backtest(
    factor_name="developer_velocity",
    universe=tech_stocks,
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
    rebalance_freq="monthly",
    top_n=5
)
```

---

## Best Practices

1. **Universe Selection**: Include at least 20-30 stocks for meaningful results
2. **Time Period**: Use at least 1 year of data; 2-3 years preferred
3. **Transaction Costs**: Set realistic costs (0.1% = 0.001 is reasonable)
4. **Rebalance Frequency**: Weekly/monthly reduces turnover vs daily
5. **Top N**: Smaller N = more concentrated, higher risk/reward
6. **Out-of-Sample Testing**: Don't overfit to historical data

# API Overview

The Alternative Data Platform provides a RESTful JSON API for accessing quantitative factors and alternative data.

## Base URL

```
http://localhost:8000  # Development
https://api.altdata.example.com  # Production
```

## Authentication

All protected endpoints require an API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" https://api.altdata.example.com/api/v1/factors
```

See [Authentication](../getting-started/authentication.md) for details.

## Response Format

All responses are JSON:

```json
{
  "data": { ... },
  "meta": {
    "total": 100,
    "page": 1,
    "page_size": 50
  }
}
```

## Error Responses

Errors return appropriate HTTP status codes with a `detail` field:

```json
{
  "detail": "Factor not found"
}
```

| Status Code | Description |
|-------------|-------------|
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid or missing API key |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Invalid request body |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

## Pagination

List endpoints support pagination:

```bash
GET /api/v1/entities?page=1&page_size=50
```

Response includes pagination metadata:

```json
{
  "entities": [...],
  "total": 1000,
  "page": 1,
  "page_size": 50
}
```

## Date Formats

Dates should be provided in ISO 8601 format:

- Date: `2024-01-15`
- DateTime: `2024-01-15T10:30:00`
- DateTime with timezone: `2024-01-15T10:30:00Z`

## Endpoints Summary

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (no auth required) |
| GET | `/` | API information |

### Factors

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/factors` | List all factors |
| GET | `/api/v1/factors/{name}` | Get factor values |
| GET | `/api/v1/categories` | List factor categories |

### Entities

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/entities` | List and search entities |
| GET | `/api/v1/entities/{id}` | Get entity details |

### Data Sources

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/sources` | List data sources |

### Aviation (Phase 1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/aviation/flights` | Get corporate flight data |

### Energy (Phase 1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/energy/load` | Get power grid load data |

### Patents (Phase 1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/patents/filings` | Get patent filings |

### Environment (Phase 1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/environment/air-quality` | Get air quality data |

### Weather (Phase 2)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/weather/observations` | Get weather observations |
| GET | `/api/v1/weather/forecast` | Get weather forecasts |

### Trends (Phase 2)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/trends/interest` | Get Google Trends data |

### Sentiment (Phase 2)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/sentiment/ticker` | Get sentiment data |

### Shipping (Phase 2)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/shipping/ports` | List tracked ports |
| GET | `/api/v1/shipping/congestion` | Get port congestion data |

### GitHub (Phase 2)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/github/repos` | List tracked repositories |
| GET | `/api/v1/github/activity` | Get repository activity |

### Satellite (Phase 2)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/satellite/parking` | Get parking lot data |
| GET | `/api/v1/satellite/agriculture` | Get agricultural NDVI data |

## Common Parameters

### Date Filtering

Most endpoints support date filtering:

```
?start_date=2024-01-01&end_date=2024-06-30
```

### Entity Filtering

Filter by entity:

```
?entity_id=AAPL
```

### Category Filtering

Filter factors by category:

```
?category=sec
```

## Rate Limiting

See [Rate Limits](../getting-started/rate-limits.md) for details on request limits.

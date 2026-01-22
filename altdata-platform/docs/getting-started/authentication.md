# Authentication

The Alternative Data Platform uses API key authentication for all protected endpoints.

## API Keys

All requests to protected endpoints must include an API key in the `X-API-Key` header.

### Using API Keys

=== "cURL"
    ```bash
    curl -H "X-API-Key: your-api-key" \
      http://localhost:8000/api/v1/factors
    ```

=== "Python SDK"
    ```python
    from altdata import AltDataClient

    client = AltDataClient(api_key="your-api-key")
    factors = client.list_factors()
    ```

=== "Python Requests"
    ```python
    import requests

    headers = {"X-API-Key": "your-api-key"}
    response = requests.get(
        "http://localhost:8000/api/v1/factors",
        headers=headers
    )
    ```

## Public Endpoints

The following endpoints do not require authentication:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /` | API information |

## Protected Endpoints

All other endpoints require a valid API key:

- `GET /api/v1/factors` - List factors
- `GET /api/v1/factors/{name}` - Get factor values
- `GET /api/v1/entities` - List entities
- `GET /api/v1/entities/{id}` - Get entity details
- `GET /api/v1/sources` - List data sources

## Error Responses

### Missing API Key

```json
{
  "detail": "API key required"
}
```

HTTP Status: `401 Unauthorized`

### Invalid API Key

```json
{
  "detail": "Invalid API key"
}
```

HTTP Status: `401 Unauthorized`

## Best Practices

1. **Never commit API keys** - Use environment variables
2. **Rotate keys regularly** - Update keys periodically
3. **Use separate keys** - Different keys for development and production
4. **Monitor usage** - Track API calls to detect unauthorized use

## Environment Variables

Store your API key in an environment variable:

```bash
export ALTDATA_API_KEY="your-api-key"
```

Then use it in your code:

```python
import os
from altdata import AltDataClient

client = AltDataClient(api_key=os.environ["ALTDATA_API_KEY"])
```

## SDK Error Handling

The Python SDK provides specific exceptions for authentication errors:

```python
from altdata import AltDataClient, AuthenticationError

client = AltDataClient(api_key="invalid-key")

try:
    factors = client.list_factors()
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
```

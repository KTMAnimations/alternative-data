# Entities API

The Entities API provides access to the entities (companies, regions, etc.) tracked in the platform.

## List Entities

List and search entities with pagination.

```
GET /api/v1/entities
```

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search` | string | - | Search by name or ticker |
| `entity_type` | string | - | Filter by entity type |
| `page` | int | 1 | Page number (1-indexed) |
| `page_size` | int | 50 | Results per page (1-100) |

### Response

```json
{
  "entities": [
    {
      "id": "AAPL",
      "name": "Apple Inc.",
      "ticker": "AAPL",
      "entity_type": "company",
      "sector": "Technology",
      "industry": "Consumer Electronics"
    },
    {
      "id": "MSFT",
      "name": "Microsoft Corporation",
      "ticker": "MSFT",
      "entity_type": "company",
      "sector": "Technology",
      "industry": "Software"
    }
  ],
  "total": 500,
  "page": 1,
  "page_size": 50
}
```

### Example

=== "cURL"
    ```bash
    # List all entities
    curl -H "X-API-Key: your-api-key" \
      "http://localhost:8000/api/v1/entities"

    # Search for entities
    curl -H "X-API-Key: your-api-key" \
      "http://localhost:8000/api/v1/entities?search=Apple"

    # Filter by type
    curl -H "X-API-Key: your-api-key" \
      "http://localhost:8000/api/v1/entities?entity_type=company"

    # Paginate
    curl -H "X-API-Key: your-api-key" \
      "http://localhost:8000/api/v1/entities?page=2&page_size=25"
    ```

=== "Python SDK"
    ```python
    from altdata import AltDataClient

    client = AltDataClient(api_key="your-api-key")

    # List all entities
    entities = client.list_entities()
    print(f"Total entities: {entities.total}")

    # Search for entities
    results = client.list_entities(search="Apple")
    for entity in results.entities:
        print(f"{entity.name} ({entity.ticker})")

    # Convert to DataFrame
    df = entities.to_dataframe()
    ```

---

## Get Entity

Get details for a specific entity by ID or ticker.

```
GET /api/v1/entities/{entity_id}
```

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `entity_id` | string | Entity ID or ticker symbol |

### Response

```json
{
  "id": "AAPL",
  "name": "Apple Inc.",
  "ticker": "AAPL",
  "entity_type": "company",
  "sector": "Technology",
  "industry": "Consumer Electronics"
}
```

### Example

=== "cURL"
    ```bash
    curl -H "X-API-Key: your-api-key" \
      http://localhost:8000/api/v1/entities/AAPL
    ```

=== "Python SDK"
    ```python
    from altdata import AltDataClient

    client = AltDataClient(api_key="your-api-key")

    entity = client.get_entity("AAPL")
    print(f"Name: {entity.name}")
    print(f"Sector: {entity.sector}")
    print(f"Industry: {entity.industry}")
    ```

---

## Entity Types

The platform tracks several types of entities:

| Type | Description | Example |
|------|-------------|---------|
| `company` | Public companies | Apple Inc. (AAPL) |
| `region` | Geographic regions | US, California |
| `port` | Shipping ports | Los Angeles Port |
| `airport` | Airports | SFO, LAX |
| `commodity` | Commodities | WTI Crude, Natural Gas |

---

## Entity Response Models

### EntityResponse

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique entity identifier |
| `name` | string | Entity name |
| `ticker` | string | Stock ticker (for companies) |
| `entity_type` | string | Type of entity |
| `sector` | string | Sector (for companies) |
| `industry` | string | Industry (for companies) |

### EntityListResponse

| Field | Type | Description |
|-------|------|-------------|
| `entities` | array | List of EntityResponse objects |
| `total` | int | Total number of entities |
| `page` | int | Current page number |
| `page_size` | int | Results per page |

---

## Error Responses

### Entity Not Found

```json
{
  "detail": "Entity not found: UNKNOWN"
}
```

HTTP Status: `404 Not Found`

---

## Searching Tips

### Search by Name

Search matches against entity name and ticker:

```bash
# Finds "Apple Inc."
curl "http://localhost:8000/api/v1/entities?search=Apple"

# Finds by ticker
curl "http://localhost:8000/api/v1/entities?search=AAPL"
```

### Case Insensitive

Searches are case-insensitive:

```bash
# These all find Apple Inc.
curl "http://localhost:8000/api/v1/entities?search=apple"
curl "http://localhost:8000/api/v1/entities?search=APPLE"
curl "http://localhost:8000/api/v1/entities?search=aapl"
```

### Partial Matching

Searches use partial matching:

```bash
# Finds "Microsoft", "Microsemi", etc.
curl "http://localhost:8000/api/v1/entities?search=micro"
```

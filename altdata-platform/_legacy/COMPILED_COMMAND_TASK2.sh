#!/bin/bash
# COMPILED RALPH COMMAND
# Copy the entire command below and run it

# TASK 2: Python SDK (Recommended first - smallest scope)
ralph "You are an expert software engineer building the Alternative Data Platform.

REPO: https://github.com/KTMAnimations/alternative-data
STATUS: Phase 1 & 2 complete | 200+ tests | 80+ factors | API at localhost:8000
STACK: Python 3.11, FastAPI, PostgreSQL+TimescaleDB, Redis, SQLAlchemy

CURRENT TASK: Create Python SDK

Create a pip-installable SDK in altdata-sdk/ directory.

REQUIRED FILES:
altdata-sdk/
├── altdata/
│   ├── __init__.py         # from .client import AltDataClient
│   ├── client.py           # Main client class
│   ├── models.py           # Pydantic response models
│   └── exceptions.py       # AltDataError, AuthError, RateLimitError
├── tests/
│   └── test_client.py      # 90%+ coverage
├── pyproject.toml          # Modern packaging config
└── README.md               # Usage examples

CLIENT INTERFACE:
\`\`\`python
from altdata import AltDataClient

client = AltDataClient(api_key='xxx', base_url='http://localhost:8000')

# List factors
factors = client.list_factors(category='sec')

# Get factor values - returns FactorData with .to_dataframe()
data = client.get_factor('insider_transaction_momentum', entity_id='AAPL', 
                          start_date='2024-01-01', end_date='2024-06-30')
df = data.to_dataframe()  # pandas DataFrame

# Entities
entities = client.list_entities(entity_type='company', search='Apple')
entity = client.get_entity('AAPL')

# Source status
status = client.get_source_status()
\`\`\`

API ENDPOINTS TO WRAP:
- GET /api/v1/factors
- GET /api/v1/factors/{name}?entity_id=X&start_date=Y&end_date=Z
- GET /api/v1/entities?entity_type=X&search=Y
- GET /api/v1/entities/{id}
- GET /api/v1/sources/status
- GET /health

SUCCESS CRITERIA:
1. pip install -e . works
2. All API endpoints wrapped
3. Returns Pydantic models with type hints
4. .to_dataframe() returns pandas DataFrame
5. Custom exceptions raised on errors
6. pytest tests/ passes with 90%+ coverage

START: cd to repo, examine src/api/main.py for endpoint signatures, then create the SDK."

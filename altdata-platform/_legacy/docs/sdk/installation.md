# SDK Installation

Install the Alternative Data Platform Python SDK.

## Requirements

- Python 3.9 or higher
- pip or another Python package manager

## Installation

### From PyPI

```bash
pip install altdata
```

### From Source

```bash
git clone https://github.com/KTMAnimations/alternative-data.git
cd alternative-data/altdata-sdk
pip install -e .
```

### With Development Dependencies

```bash
pip install altdata[dev]
```

This includes pytest, coverage, and other testing tools.

## Dependencies

The SDK has minimal dependencies:

| Package | Version | Purpose |
|---------|---------|---------|
| httpx | ≥0.25.0 | HTTP client |
| pydantic | ≥2.0.0 | Data validation |
| pandas | ≥2.0.0 | DataFrame support |

## Verification

Verify the installation:

```python
import altdata
print(altdata.__version__)
```

## Quick Test

```python
from altdata import AltDataClient

# Create client
client = AltDataClient(
    api_key="your-api-key",
    base_url="http://localhost:8000"
)

# Check health
health = client.health()
print(f"API Status: {health.status}")

# Clean up
client.close()
```

## Virtual Environment

We recommend using a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install SDK
pip install altdata
```

## Upgrading

```bash
pip install --upgrade altdata
```

## Uninstalling

```bash
pip uninstall altdata
```

## Next Steps

- [Usage Guide](usage.md) - Learn how to use the SDK
- [Examples](examples.md) - Code examples

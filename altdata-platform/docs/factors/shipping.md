# Shipping Factors

Factors derived from port congestion and vessel tracking data.

## Overview

Shipping factors capture global trade flows and supply chain conditions through port activity monitoring.

**Data Source**: MarineTraffic, AIS data
**Update Frequency**: Daily
**Entity Type**: Port/Region

---

## Factors

### port_congestion_index

**Description**: Composite congestion score (0-1)

**Signal Logic**: Higher congestion indicates supply chain stress

---

### vessels_waiting

**Description**: Number of vessels waiting at anchor

---

### average_wait_time

**Description**: Average vessel wait time in hours

---

### container_throughput

**Description**: Estimated container throughput

---

### congestion_trend

**Description**: 30-day trend in congestion

---

### port_efficiency_score

**Description**: Efficiency relative to historical average

---

## Example Usage

```python
from altdata import AltDataClient
from datetime import date

client = AltDataClient(api_key="your-api-key")

# Get congestion data
data = client.get_factor(
    "port_congestion_index",
    entity_id="USLAX",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# List ports
ports = client.list_ports(country="US")
for port in ports.ports:
    print(f"{port.port_name}: {port.port_id}")

# Get congestion for specific date
congestion = client.get_port_congestion(date(2024, 1, 15), port_id="USLAX")
cong_df = congestion.to_dataframe()
print(cong_df.head())
```

---

## Major Ports Tracked

| Port ID | Name | Region |
|---------|------|--------|
| USLAX | Los Angeles | US West Coast |
| USLGB | Long Beach | US West Coast |
| USNYC | New York/New Jersey | US East Coast |
| CNSGH | Shanghai | China |
| CNSZX | Shenzhen | China |
| SGSIN | Singapore | Asia |
| NLRTM | Rotterdam | Europe |

---

## Data Quality Notes

- AIS coverage varies by region
- Some vessels disable transponders
- Container counts are estimated
- Weather affects operations

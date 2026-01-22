# Energy Factors

Factors derived from power grid load data from ISO/RTO operators.

## Overview

Energy factors capture electricity demand patterns, which correlate with economic activity and can provide early signals of industrial production changes.

**Data Source**: EIA, CAISO, ERCOT, PJM, MISO
**Update Frequency**: Hourly
**Entity Type**: Region (ISO region)

---

## Factors

### grid_load_anomaly

**Description**: Current load vs. historical average for same hour/day

**Signal Logic**: Higher-than-expected load may indicate economic activity

---

### demand_forecast_error

**Description**: Actual load minus forecasted load

**Signal Logic**: Consistent under-forecasting may signal economic acceleration

---

### peak_load_trend

**Description**: Rolling trend in daily peak load

---

### load_variability

**Description**: Intraday load variability (standard deviation)

---

### industrial_load_proxy

**Description**: Estimated industrial load (total minus residential estimate)

---

### renewable_penetration

**Description**: Percentage of load from renewable sources

---

### capacity_utilization

**Description**: Current load as percentage of available capacity

---

### load_growth_rate

**Description**: Year-over-year load growth

---

## Example Usage

```python
from altdata import AltDataClient
from datetime import date

client = AltDataClient(api_key="your-api-key")

# Get grid load data
data = client.get_factor(
    "grid_load_anomaly",
    entity_id="CAISO",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# Get raw load data
load = client.get_grid_load("CAISO", date(2024, 1, 15))
load_df = load.to_dataframe()
print(load_df.head())
```

---

## Regional Coverage

| ISO | Region | Coverage |
|-----|--------|----------|
| CAISO | California | Full state |
| ERCOT | Texas | ~90% of state |
| PJM | Mid-Atlantic | 13 states |
| MISO | Midwest | 15 states |

---

## Data Quality Notes

- Data available with ~1 hour lag
- Forecasts are day-ahead
- Weather normalization recommended for analysis
- Holiday patterns differ by region
